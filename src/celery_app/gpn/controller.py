import copy
import math
import time
from datetime import datetime
from typing import Dict, Any, List

from sqlalchemy import select as sa_select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, aliased, contains_eager, selectinload

from src.celery_app.exceptions import CeleryError
from src.celery_app.gpn.api import GPNApi, GpnGoodsCategory
from src.celery_app.irrelevant_balances import IrrelevantBalances
from src.celery_app.group_limit_order import GroupLimitOrder
from src.celery_app.transaction_helper import get_local_cards, get_local_card
from src.config import TZ, PRODUCTION
from src.database.models import CompanyOrm, CardLimitOrm, AzsOrm, RegionOrm, TariffNewOrm, InnerGoodsGroupOrm, \
    GroupLimitOrm, CardGroupOrm
from src.database.models.azs import AzsOwnType
from src.database.models.balance import BalanceOrm as BalanceOrm
from src.database.models.balance_system import BalanceSystemOrm
from src.database.models.card import CardOrm, BlockingCardReason, CardHistoryOrm
from src.database.models.card_type import CardTypeOrm
from src.database.models.goods import OuterGoodsOrm
from src.database.models.goods_category import GoodsCategory
from src.database.models.system import CardSystemOrm, SystemOrm
from src.database.models.transaction import TransactionOrm
from src.repositories.base import BaseRepository
from src.repositories.card import CardRepository
from src.repositories.company import CompanyRepository
from src.repositories.goods import GoodsRepository
from src.repositories.system import SystemRepository
from src.repositories.tariff import TariffRepository
from src.repositories.transaction import TransactionRepository
from src.utils.common import calc_available_balance
from src.utils.enums import ContractScheme, TransactionType, System
from src.utils.loggers import get_logger


class GPNController(BaseRepository):

    def __init__(self, session: AsyncSession):
        super().__init__(session, None)
        self.logger = get_logger(name="GPNController", filename="celery.log")
        self.api = GPNApi()
        self.system = None
        self._irrelevant_balances = IrrelevantBalances(system=System.GPN)
        self.card_groups = None
        self.card_types = {}

        self._local_cards: List[CardOrm] = []
        self._bst_list: List[BalanceSystemOrm] = []
        self._outer_goods_list: List[OuterGoodsOrm] = []
        self._card_history: List[CardHistoryOrm] = []
        self._azs_stations: List[AzsOrm] = []
        self._tariffs: List[TariffNewOrm] = []

    async def init_system(self) -> None:
        if not self.system:
            system_repository = SystemRepository(self.session)
            self.system = await system_repository.get_system_by_short_name(
                short_name=System.GPN.value,
                scheme=ContractScheme.OVERBOUGHT
            )

    async def sync(self) -> IrrelevantBalances:
        await self.init_system()

        # Прогружаем наш баланс
        await self.load_balance()

        # Синхронизируем карты по номеру
        # await self.sync_cards()

        # Прогружаем транзакции
        await self.load_transactions()

        # Возвращаем объект со списком транзакций, начиная с которых требуется пересчитать балансы
        return self._irrelevant_balances

    async def load_balance(self) -> None:
        contract_data = self.api.contract_info()
        balance = float(contract_data['balanceData']['available_amount'])
        self.logger.info('Наш баланс в системе {}: {} руб.'.format(self.system.full_name, balance))

        # Обновляем запись в локальной БД
        await self.update_object(self.system, update_data={
            "balance": balance,
            "balance_sync_dt": datetime.now(tz=TZ)
        })

    async def service_sync(self) -> None:
        """
        1. Синхронизируем группы карт
        2. Синхронизируем карты
        3. Устанавливаем лимиты на группы.
        4. Сверяем в правильных ли группах находятся карты и в ГПН разносим карты по группам в соответствии с
        принадлежностью карт в локальной БД
        """

        # ---- 1 ----

        # Получаем список карт от системы ГПН
        remote_cards = self.api.get_gpn_cards()
        self.logger.info(f"Количество карт в API ГПН: {len(remote_cards)}")

        # Синхронизируем группы карт
        await self.sync_card_groups(remote_cards)

        # ---- 2 ----

        # Синхронизируем карты
        await self.sync_cards(remote_cards)

        # ---- 3 ----
        # Устанавливаем лимиты на группы
        self.logger.info("Запускаю синхронизацию лимитов на группы карт")
        await self.sync_group_limits()

    async def get_card_types(self, gpn_cards: List[Dict[str, Any]]) -> None:
        """
        Получаем из локальной БД список типов карт, соответствующих типам карт в ГПН.
        Если в локальной БД не найдено, то создаем новые типы.
        """
        gpn_card_type_names = [card["carrier_name"] for card in gpn_cards]
        stmt = sa_select(CardTypeOrm).where(CardTypeOrm.name.in_(gpn_card_type_names))
        local_card_types_dataset = await self.select_all(stmt)

        if len(gpn_card_type_names) != len(local_card_types_dataset):
            local_card_type_names = [ct.name for ct in local_card_types_dataset]
            new_card_types = []
            for gpn_card_type_name in gpn_card_type_names:
                if gpn_card_type_name not in local_card_type_names:
                    new_card_types.append({"name": gpn_card_type_name})

            await self.bulk_insert_or_update(CardTypeOrm, new_card_types, index_field="name")

            stmt = sa_select(CardTypeOrm).where(CardTypeOrm.name.in_(gpn_card_type_names))
            local_card_types_dataset = await self.select_all(stmt)

        self.card_types = {data.name: data for data in local_card_types_dataset}

    async def sync_card_groups(self, remote_cards: List[Dict[str, Any]]) -> None:
        self.logger.info("Запускаю синхронизацию групп карт")
        # Из локальной БД получаем список организаций, которым присвоены карты ГПН.
        stmt = (
            sa_select(CompanyOrm)
            .options(
                selectinload(CompanyOrm.card_groups)
            )
            .select_from(CompanyOrm, CardOrm, CardSystemOrm)
            .where(CompanyOrm.id == CardOrm.company_id)
            .where(CardOrm.id == CardSystemOrm.card_id)
            .where(CardSystemOrm.system_id == self.system.id)
        )
        companies = await self.select_all(stmt)

        # Из API получаем список групп карт
        gpn_groups = self.api.get_card_groups()

        # Сравниваем непосредственно группы карт.
        # Если в БД отсутствует запись о группе, создаем её.
        # Сверенные группы удаляем из списков для уменьшения стоимости алгоритма.
        i = 0
        while i < len(companies):
            company = companies[i]
            found = False
            for gpn_group in gpn_groups:
                if gpn_group['name'] == company.personal_account:
                    # В списке из БД найдена организация с ЛС, соответствующим наименованием группы в ГПН.
                    found = True

                    # Проверяем существование записи о группе в локальной БД
                    if not company.has_card_group(self.system.id):
                        card_group = CardGroupOrm(
                            system_id=self.system.id,
                            external_id=gpn_group["id"],
                            name=company.personal_account,
                            company_id=company.id
                        )
                        await self.save_object(card_group)
                        self.logger.info(f"В БД создана группа карт системы ГПН для организации {company.name}")

                    # Сокращаем списки
                    companies.remove(company)
                    gpn_groups.remove(gpn_group)
                    break

            if not found:
                # Совпадающая группа НЕ найдена, переходим к следующей.
                i += 1

        if PRODUCTION:
            # Удаляем в API избыточные группы.
            for group in gpn_groups:
                # В ГПН открепляем карты от группы
                self.api.unbind_cards_from_group(
                    card_numbers=[card['number'] for card in remote_cards if card['group_id'] == group['id']],
                    card_external_ids=[card['id'] for card in remote_cards if card['group_id'] == group['id']],
                    group_id=group['id']
                )

                # Удаляем группу ГПН
                self.api.delete_gpn_group(group_id=group['id'], group_name=group['name'])

            # Создаем в API и в БД недостающие группы.
            for company in companies:
                group_id = self.api.create_card_group(company.personal_account)
                card_group = CardGroupOrm(
                    system_id=self.system.id,
                    external_id=group_id,
                    name=company.personal_account,
                    company_id=company.id
                )
                await self.save_object(card_group)
                self.logger.info(f"В БД создана группа карт системы ГПН для организации {company.name}")

    async def sync_cards(self, remote_cards: List[Dict[str, Any]]) -> None:
        # Получаем типы карт
        await self.get_card_types(remote_cards)

        # Получаем список карт из БД
        local_cards = await get_local_cards(session=self.session, system_id=self.system.id)
        self.logger.info(f"Количество карт в локальной БД (до синхронизации): {len(local_cards)}")

        # Создаем в локальной БД новые карты и привязываем их к ГПН. Статус карты из ГПН транслируем на локальную БД.
        # Привязываем в локальной БД карты, открепленные от ГПН - статус не устанавливаем.
        local_card_numbers = [local_card.card_number for local_card in local_cards]
        for remote_card in remote_cards:
            if remote_card['number'] not in local_card_numbers:
                is_active = True if "locked" not in remote_card["status"].lower() else False
                await self.bind_or_create_card(
                    card_number=remote_card['number'],
                    card_type_name=remote_card["carrier_name"],
                    is_active=is_active
                )

        # Из локальной БД заново получаем список карт, привязанных к ГПН
        local_cards = await get_local_cards(session=self.session, system_id=self.system.id)
        self.logger.info(f"Количество карт в локальной БД (после синхронизации): {len(local_cards)}")

        # Из API получаем группы карт
        gpn_card_groups = self.api.get_card_groups()
        gpn_group_id_by_name = {gpn_card_group['name']: gpn_card_group['id'] for gpn_card_group in gpn_card_groups}
        gpn_group_name_by_id = {gpn_card_group['id']: gpn_card_group['name'] for gpn_card_group in gpn_card_groups}

        # Сравниваем ЛС организаций, которым принадлежат карты с группами ГПН.
        # Записи в локальной БД имеют первичное значение.

        # Открепляем от групп карты, которые в них не должны состоять
        gpn_cards_dict = {card['number']: card for card in remote_cards}
        for local_card in local_cards:
            gpn_card = gpn_cards_dict[local_card.card_number]
            print('UUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUU')
            print(gpn_card)
            if not local_card.company_id \
                    or local_card.company.personal_account != gpn_group_name_by_id[gpn_card['group_id']]:
                self.api.unbind_cards_from_group(
                    card_numbers=[local_card.card_number],
                    card_external_ids=[local_card.external_id],
                    group_id=gpn_card['group_id']
                )

        # Прикрепляем к группам карты, которые должны в них состоять, но не состоят
        binding_data = {}
        for local_card in local_cards:
            gpn_card = gpn_cards_dict[local_card.card_number]
            if local_card.company_id:
                true_group_id = gpn_group_id_by_name[local_card.company.personal_account]
                if gpn_card['group_id'] != true_group_id:
                    if true_group_id in binding_data:
                        binding_data[true_group_id].append(gpn_card['id'])
                    else:
                        binding_data[true_group_id] = [gpn_card['id']]

        for group_id, card_external_ids in binding_data.items():
            self.api.bind_cards_to_group(
                card_numbers=[local_card.card_number for local_card in local_cards
                              if local_card.external_id in card_external_ids],
                card_external_ids=card_external_ids,
                group_id=group_id
            )

        # Записываем в БД время последней успешной синхронизации
        await self.update_object(self.system, update_data={"cards_sync_dt": datetime.now(tz=TZ)})
        self.logger.info('Синхронизация карт выполнена')

    async def sync_group_limits(self):
        # Из локальной БД получаем список организаций, которым присвоены карты ГПН.
        stmt = (
            sa_select(CompanyOrm)
            .options(
                selectinload(CompanyOrm.card_groups)
            )
            .options(
                selectinload(CompanyOrm.group_limits)
            )
            .options(
                selectinload(CompanyOrm.balances)
            )
            .select_from(CompanyOrm, CardOrm, CardSystemOrm)
            .where(CompanyOrm.id == CardOrm.company_id)
            .where(CardOrm.id == CardSystemOrm.card_id)
            .where(CardSystemOrm.system_id == self.system.id)
        )
        companies = await self.select_all(stmt)

        # Сверяем групповые лимиты
        for company in companies:
            # Из ГПН получаем лимиты по группе карт
            group: CardGroupOrm = company.get_card_group()
            gpn_group_limits = self.api.get_card_group_limits(group.external_id)
            for gpn_category in GpnGoodsCategory:
                # Предполагается, что локально сохраненные лимиты присутствуют в ГПН.
                # Проверяем наличие лимита в БД.
                found_locally = False
                for local_limit in company.group_limits:
                    if local_limit.system_id == self.system.id \
                            and local_limit.inner_goods_category == gpn_category.value["local_category"]:
                        found_locally = True
                        break

                if not found_locally:
                    # Если лимит не найден в БД, то проверяем его наличие в ГПН
                    found_remotely = False
                    for remote_limit in gpn_group_limits:
                        if remote_limit["productType"] == gpn_category.value["id"]:
                            found_remotely = True
                            # Импортируем сведения о лимите в БД
                            limit_dataset = {
                                "system_i": self.system.id,
                                "external_id": remote_limit["id"],
                                "company_id": company.id,
                                "limit_sum": remote_limit["sum"]["value"],
                                "inner_goods_category": gpn_category.value["local_category"]
                            }
                            await self.insert(GroupLimitOrm, **limit_dataset)
                            self.logger("Лимит записан в локальную БД")
                            break

                    if not found_remotely:
                        # Если лимит не установлен ни в ГПН, ни локально, то создаем его в обеих локациях

                        available_balance = calc_available_balance(
                            current_balance=company.overbought_balance().balance,
                            min_balance=company.min_balance,
                            overdraft_on=company.overdraft_on,
                            overdraft_sum=company.overdraft_sum
                        )

                        limit_sum = available_balance if gpn_category == GpnGoodsCategory.FUEL else 1.0
                        limit_sum = int(math.floor(limit_sum))

                        group = company.get_card_group()

                        if PRODUCTION:
                            # Создаем лимит в ГПН
                            remote_limit_id = self.api.set_group_limit(
                                limit_id=None,
                                group_id=group.external_id,
                                product_category=gpn_category,
                                limit_sum=limit_sum
                            )
                            # Записываем лимит в локальную БД
                            limit_dataset = {
                                "system_id": self.system.id,
                                "external_id": remote_limit_id,
                                "company_id": company.id,
                                "limit_sum": limit_sum,
                                "inner_goods_category": gpn_category.value["local_category"]
                            }
                            await self.insert(GroupLimitOrm, **limit_dataset)
                            self.logger("Лимит записан в локальную БД")

    async def bind_or_create_card(self, card_number: str, card_type_name: str, is_active: bool) -> None:
        stmt = sa_select(CardOrm).where(CardOrm.card_number == card_number)
        card = await self.select_first(stmt)
        if card:
            # Карта существует, но она не привязана к ГПН. Привязываем её.
            card_system_date = {"card_id": card.id, "system_id": self.system.id}
            await self.insert(CardSystemOrm, **card_system_date)
            self.logger.info(f"Cуществующая в БД карта {card_number} привязана к системе ГПН")

        else:
            # Карта не существует в локальной БД. Создаем её.
            new_card_data = {
                "card_number": card_number,
                "card_type_id": self.card_types[card_type_name].id,
                "is_active": is_active,
            }
            new_card = await self.insert(CardOrm, **new_card_data)

            # Привязываем к системе
            card_system_date = {"card_id": new_card.id, "system_id": self.system.id}
            await self.insert(CardSystemOrm, **card_system_date)

            self.logger.info(f"В БД создана новая карта ГПН {card_number}")

    """
    async def gpn_bind_company_to_cards(self, card_ids: List[str], personal_account: str,
                                        company_available_balance: int | float) -> None:
        await self.init_system()

        # Получаем из ГПН группу с наименованием, содержащим personal account
        # Если нет такой, то создаем.
        group_id = None
        # Из API получаем список групп карт
        groups = self.api.get_card_groups()
        for group in groups:
            if group['name'] == personal_account:
                group_id = group['id']
                break

        if not group_id:
            group_id = self.api.create_card_group(personal_account)
            current_company_limits = self.api.get_card_group_limits(group_id)
            limit_sum = self.calc_limit_sum(
                company_available_balance=company_available_balance,
                current_company_limits=current_company_limits
            )
            self.set_company_limits(
                group_id=group_id,
                current_company_limits=current_company_limits,
                limit_sum=limit_sum
            )

        # Привязываем карту к группе в API ГПН
        stmt = sa_select(CardOrm).where(CardOrm.id.in_(card_ids)).order_by(CardOrm.card_number)
        cards = await self.select_all(stmt)
        card_external_ids = [card.external_id for card in cards]
        self.api.bind_cards_to_group(card_external_ids=card_external_ids, group_id=group_id)

        # Привязываем карты к группе в локальной БД
        dataset = [
            {
                "id": card.id,
                "group_id": group_id
            } for card in cards
        ]
        await self.bulk_update(CardOrm, dataset)
    """

    """
    async def gpn_unbind_company_from_cards(self, card_ids: List[str]) -> None:
        await self.init_system()

        stmt = sa_select(CardOrm).where(CardOrm.id.in_(card_ids)).order_by(CardOrm.card_number)
        cards = await self.select_all(stmt)
        card_external_ids = [card.external_id for card in cards]

        # Отвязываем карту от группы в API ГПН
        self.api.unbind_cards_from_group(card_external_ids=card_external_ids)

        # Устанавливаем статус карты в API ГПН
        self.api.block_cards(card_external_ids)
    """

    async def set_card_states(self, balance_ids_to_change_card_states: Dict[str, List[str]]):
        # В функцию переданы ID балансов, картам которых нужно сменить состояние (заблокировать или разблокировать).
        # Меняем статус в локальной БД, потом устанавливаем новый статус в системе поставщика.
        await self.init_system()

        # Получаем карты из локальной БД
        card_repository = CardRepository(self.session, None)
        local_cards_to_activate = await card_repository.get_cards_by_filters(
            balance_ids=balance_ids_to_change_card_states["to_activate"],
            system_id=self.system.id
        )
        local_cards_to_activate = [card for card in local_cards_to_activate
                                   if not card.is_active and card.reason_for_blocking != BlockingCardReason.PIN]
        local_cards_to_block = await card_repository.get_cards_by_filters(
            balance_ids=balance_ids_to_change_card_states["to_block"],
            system_id=self.system.id
        )
        local_cards_to_block = [card for card in local_cards_to_block if card.is_active]

        # Обновляем состояние карт в локальной БД
        if local_cards_to_activate or local_cards_to_block:
            dataset = [
                {
                    "id": card.id,
                    "is_active": True,
                    "reason_for_blocking": None
                } for card in local_cards_to_activate
            ]
            dataset.extend([
                {
                    "id": card.id,
                    "is_active": False,
                    "reason_for_blocking": BlockingCardReason.NNK
                } for card in local_cards_to_block
            ])
            await self.bulk_update(CardOrm, dataset)

        # Устанавливаем статусы карт в системе поставщика
        if local_cards_to_activate:
            ext_card_ids = [card.external_id for card in local_cards_to_activate]
            self.api.activate_cards(ext_card_ids)

        if local_cards_to_block:
            ext_card_ids = [card.external_id for card in local_cards_to_block]
            self.api.block_cards(ext_card_ids)

    async def set_group_limits_by_balance_ids(self, balance_ids: List[str] | None, force: bool = False) -> None:
        if not force and not balance_ids:
            # Если force установлен в False, то выполняется алгоритм для установки лимитов после пересчета балансов.
            # Если True, то выполняется алгоритм для установки лимитов при выполнении синхронизации карт и групп.
            print("Получен пустой список балансов для обновления лимитов на группы карт ГПН")
            return None

        await self.init_system()

        # Получаем параметры балансов и организаций
        company_tbl = aliased(CompanyOrm, name="org")
        stmt = (
            sa_select(BalanceOrm)
            .options(
                joinedload(BalanceOrm.company)
            )
            .select_from(BalanceOrm, company_tbl, CardOrm, CardSystemOrm)
            .where(BalanceOrm.scheme == ContractScheme.OVERBOUGHT)
            .where(company_tbl.id == BalanceOrm.company_id)
            .where(CardOrm.company_id == company_tbl.id)
            .where(CardSystemOrm.card_id == CardOrm.id)
            .where(CardSystemOrm.system_id == self.system.id)
        )
        if balance_ids:
            stmt = stmt.where(BalanceOrm.id.in_(balance_ids))

        balances = await self.select_all(stmt)

        # Получаем из API список всех групп карт
        groups = self.api.get_card_groups()

        def get_group_id_by_name(group_name: str) -> str:
            for g in groups:
                if g['name'] == group_name:
                    return g['id']

        j = 1
        companies_amount = len(balances)
        for balance in balances:
            self.logger.info("------")
            self.logger.info(f"Организация {j} из {companies_amount}: {balance.company.personal_account}")
            j += 1

            # if balance.company.personal_account == "9229609":
            #     print("Найден баланс организации ОВР")

            # Получаем идентификатор группы карт
            group_id = get_group_id_by_name(balance.company.personal_account)
            if not group_id:
                group_id = self.api.create_card_group(balance.company.personal_account)

            # if balance.company.personal_account == "9229609":
            #     print(f"Идентификатор группы ОВР: {group_id}")

            # Получаем текущие лимиты организации
            current_company_limits = self.api.get_card_group_limits(group_id)
            # if current_company_limits and balance.company.personal_account == "9229609":
            #     print(f"Действующие лимиты организации ОВР:")
            #     for current_company_limit in current_company_limits:
            #         print(current_company_limit)

            # Вычисляем новый доступный лимит на категорию "Топливо"
            # overdraft_sum = balance.company.overdraft_sum if balance.company.overdraft_on else 0
            # company_available_balance = int(balance.balance + overdraft_sum)
            company_available_balance = calc_available_balance(
                current_balance=balance.balance,
                min_balance=balance.company.min_balance,
                overdraft_on=balance.company.overdraft_on,
                overdraft_sum=balance.company.overdraft_sum
            )
            limit_sum = self.calc_limit_sum(
                company_available_balance=company_available_balance,
                current_company_limits=current_company_limits
            )
            self.logger.info(f"personal_account: {balance.company.personal_account} | "
                             f"available_balance:{company_available_balance} | limit_sum: {limit_sum}")
            # if balance.company.personal_account == "9229609":
            #     print(f"Новый лимит для организации ОВР: {limit_sum} руб")

            # Устанавливаем лимиты на группу по всем категориям
            self.set_company_limits(
                group_id=group_id,
                current_company_limits=current_company_limits,
                limit_sum=limit_sum
            )

    @staticmethod
    def calc_limit_sum(company_available_balance: int | float, current_company_limits) -> int:
        # Суммируем все произведенные расходы по каждой категории товаров
        spent_sum = 0
        for current_limit in current_company_limits:
            spent_sum += current_limit['sum']['used']

        # Вычисляем новый доступный лимит на категорию "Топливо"
        limit_sum = max(int(math.floor(company_available_balance + spent_sum)), 1)
        return limit_sum

    """Удалить"""

    def set_company_limits(self, group_id: str, current_company_limits, limit_sum: int | float):
        if isinstance(limit_sum, float):
            limit_sum = int(math.floor(limit_sum))

        # Если текущие лимиты не относятся к постоянным, то удаляем их
        i = 0
        while i < len(current_company_limits):
            current_limit = current_company_limits[i]
            if current_limit['time']['number'] != 1 or current_limit['time']['type'] != 2:
                if PRODUCTION:
                    self.api.delete_group_limit(limit_id=current_limit['id'], group_id=group_id)
                else:
                    print(f"Псевдоудален лимит на категорию | LIMIT_ID: {current_limit['id']} | GROUP_ID: {group_id}")

                current_company_limits.remove(current_limit)
            else:
                i += 1

        # Устанавливаем/изменяем лимит на категорию "Топливо"
        limit_id = None
        need_to_update = False
        for current_limit in current_company_limits:
            if current_limit['productType'] == GpnGoodsCategory.FUEL.value["id"]:
                limit_id = current_limit['id']
                if current_limit['sum']['value'] != limit_sum:
                    need_to_update = True
                    self.logger.info(f"group_id: {group_id} | gpn_limit: {current_limit['sum']['value']} | "
                                     f"local_limit: {limit_sum}")
                break

        # if group_id == "1-170U7J6K":
        #     print(f"Идентификатор нового лимита на категорию Топливо: {group_id}")

        if not limit_id or need_to_update:
            if PRODUCTION:
                self.api.set_group_limit(
                    limit_id=limit_id,
                    group_id=group_id,
                    product_category=GpnGoodsCategory.FUEL,
                    limit_sum=limit_sum
                )
            else:
                print(f"Псевдо установлен/обновлен лимит на категорию Топливо | LIMIT_ID: {limit_id} | "
                      f"GROUP_ID: {group_id} | LIMIT_SUM: {limit_sum}")

        # Устанавливаем/изменяем лимит на остальные категории
        for not_fuel_category in GpnGoodsCategory.not_fuel_categories():
            limit_id = None
            need_to_update = False
            for current_limit in current_company_limits:
                if current_limit['productType'] == not_fuel_category.value["id"]:
                    limit_id = current_limit['id']
                    if current_limit['sum']['value'] != 1:
                        need_to_update = True
                    break

            # Создаем лимит, если его не существовало.
            # Обновляем лимит, если его значение не равно 1.
            if not limit_id or need_to_update:
                if PRODUCTION:
                    self.api.set_group_limit(
                        limit_id=limit_id,
                        group_id=group_id,
                        product_category=not_fuel_category,
                        limit_sum=1
                    )
                else:
                    print(f"Псевдо установлен/обновлен лимит на категорию {not_fuel_category} | LIMIT_ID: {limit_id} | "
                          f"GROUP_ID: {group_id} | LIMIT_SUM: 1")

    async def load_transactions(self) -> None:
        await self.init_system()

        # Получаем список транзакций от поставщика услуг
        remote_transactions = self.api.get_transactions(transaction_days=self.system.transaction_days)
        self.logger.info(f'Количество транзакций от системы ГПН: {len(remote_transactions)} шт')
        if not len(remote_transactions):
            return None

        # Получаем список транзакций из локальной БД
        transaction_repository = TransactionRepository(self.session, None)
        local_transactions = await transaction_repository.get_recent_system_transactions(
            system_id=self.system.id,
            transaction_days=self.system.transaction_days
        )
        self.logger.info(f'Количество транзакций из локальной БД: {len(local_transactions)} шт')

        # Сравниваем транзакции локальные с полученными от системы.
        # Идентичные транзакции исключаем из списков.
        self.logger.info('Приступаю к процедуре сравнения локальных транзакций с полученными от системы ГПН')
        to_delete_local = []
        for local_transaction in local_transactions:
            remote_transaction = self.get_equal_remote_transaction(local_transaction, remote_transactions)
            if remote_transaction:
                remote_transactions.remove(remote_transaction)
            else:
                # Транзакция присутствует локально, но у поставщика услуг её нет.
                # Помечаем на удаление локальную транзакцию.
                to_delete_local.append(local_transaction)
                # if local_transaction.balance_id:
                self._irrelevant_balances.add(
                    balance_id=str(local_transaction.balance_id),
                    irrelevancy_date_time=local_transaction.date_time_load
                )

                # Вычисляем дельту изменения суммы баланса - понадобится позже для правильного
                # выставления лимита на группу карт
                personal_account = local_transaction.balance.company.personal_account
                if personal_account in self._irrelevant_balances.sum_deltas:
                    self._irrelevant_balances.sum_deltas[personal_account] -= local_transaction.total_sum
                else:
                    self._irrelevant_balances.sum_deltas[personal_account] = local_transaction.total_sum

        # Удаляем помеченные транзакции из БД
        self.logger.info(f'Удалить тразакции из локальной БД: {len(to_delete_local)} шт')
        if to_delete_local:
            for transaction in to_delete_local:
                await self.delete_object(TransactionOrm, transaction.id)

        # Транзакции от системы, оставшиеся необработанными, записываем в локальную БД.
        self.logger.info(f'Новые тразакции от системы ГПН: {len(remote_transactions)} шт')
        if remote_transactions:
            await self.process_new_remote_transactions(remote_transactions, transaction_repository)

        # Записываем в БД время последней успешной синхронизации
        await self.update_object(self.system, update_data={"transactions_sync_dt": datetime.now(tz=TZ)})

        # Обновляем время последней транзакции для карт
        await transaction_repository.renew_cards_date_last_use()

    @staticmethod
    def get_equal_remote_transaction(local_transaction: TransactionOrm, remote_transactions: List[Dict[str, Any]]) \
            -> Dict[str, Any] | None:
        for remote_transaction in remote_transactions:
            if str(remote_transaction['id']) == local_transaction.external_id:
                return remote_transaction

    async def process_new_remote_transactions(self, remote_transactions: List[Dict[str, Any]],
                                              transaction_repository: TransactionRepository) -> None:
        # Сортируем транзакции по времени совершения
        def sorting(tr):
            return tr['timestamp']

        remote_transactions = sorted(remote_transactions, key=sorting)

        # Получаем список продуктов / услуг
        self._outer_goods_list = await transaction_repository.get_outer_goods_list(system_id=self.system.id)

        # Получаем историю принадлежности карт
        card_repository = CardRepository(session=self.session, user=None)
        self._card_history = copy.deepcopy(await card_repository.get_card_history())

        # Получаем список АЗС
        tariff_repository = TariffRepository(session=self.session, user=None)
        self._azs_stations = copy.deepcopy(await tariff_repository.get_azs_stations(self.system.id))

        # Получаем тарифы
        self._tariffs = copy.deepcopy(await tariff_repository.get_tariffs(system_id=self.system.id))

        # Получаем карты
        card_numbers = [transaction['card_number'] for transaction in remote_transactions]
        self._local_cards = await get_local_cards(
            session=self.session,
            system_id=self.system.id,
            card_numbers=card_numbers
        )

        # Подготавливаем список транзакций для сохранения в БД
        transactions_to_save = []
        for remote_transaction in remote_transactions:
            transaction_data = await self.process_new_remote_transaction(
                card_number=remote_transaction['card_number'],
                remote_transaction=remote_transaction
            )
            if transaction_data:
                transactions_to_save.append(transaction_data)
                # if transaction_data['balance_id']:
                self._irrelevant_balances.add(
                    balance_id=str(transaction_data['balance_id']),
                    irrelevancy_date_time=transaction_data['date_time_load']
                )

        # Сохраняем транзакции в БД
        await self.bulk_insert_or_update(TransactionOrm, transactions_to_save)

    async def process_new_remote_transaction(self, card_number: str, remote_transaction: Dict[str, Any]) \
            -> Dict[str, Any] | None:
        """
        Обработка транзакции, сохранение в БД. Примеры транзакций см. в файле transaction_examples.txt
        """

        purchase = True if remote_transaction['type'] == "P" else False
        comments = ''

        # Получаем карту
        card = await get_local_card(card_number, self._local_cards)

        # Получаем баланс
        company = self.get_company_by_card_number(card_number=card_number)
        balance = company.overbought_balance()

        # Получаем продукт
        outer_goods = await self.get_outer_goods(remote_transaction)

        # Получаем АЗС
        azs = await self.get_azs(azs_external_id=remote_transaction['poi_id'])

        # Получаем тариф
        tariff = self.get_company_tariff_on_transaction_time(
            company=balance.company,
            transaction_time=remote_transaction['timestamp'],
            inner_group=outer_goods.outer_group.inner_group if outer_goods.outer_group else None,
            azs=azs
        )
        if not tariff:
            self.logger.error(f"Не удалось определить тариф для транзакции {remote_transaction}")

        # Сумма транзакции
        transaction_type = TransactionType.PURCHASE if purchase else TransactionType.REFUND
        transaction_sum = -abs(remote_transaction['sum_no_discount']) if purchase \
            else abs(remote_transaction['sum_no_discount'])

        # Сумма скидки/наценки
        discount_fee_percent = tariff.discount_fee / 100 if tariff else 0
        discount_fee_sum = transaction_sum * discount_fee_percent

        # Получаем итоговую сумму
        total_sum = transaction_sum + discount_fee_sum

        transaction_data = dict(
            external_id=str(remote_transaction['id']),
            date_time=remote_transaction['timestamp'],
            date_time_load=datetime.now(tz=TZ),
            transaction_type=transaction_type,
            system_id=self.system.id,
            card_id=card.id,
            balance_id=balance.id,
            azs_code=remote_transaction['poi_id'],
            outer_goods_id=outer_goods.id if outer_goods else None,
            fuel_volume=-remote_transaction['qty'],
            price=remote_transaction['price_no_discount'],
            transaction_sum=transaction_sum,
            tariff_new_id=tariff.id if tariff else None,
            discount_sum=discount_fee_sum if discount_fee_percent < 0 else 0,
            fee_sum=discount_fee_sum if discount_fee_percent > 0 else 0,
            total_sum=total_sum,
            company_balance_after=0,
            comments=comments,
        )

        # Вычисляем дельту изменения суммы баланса - понадобится позже для правильного
        # выставления лимита на группу карт
        if company.personal_account in self._irrelevant_balances.sum_deltas:
            self._irrelevant_balances.sum_deltas[company.personal_account] += transaction_data["total_sum"]
        else:
            self._irrelevant_balances.sum_deltas[company.personal_account] = transaction_data["total_sum"]

        # Это нужно, чтобы в БД у транзакций отличалось время и можно было корректно выбрать транзакцию,
        # которая предшествовала измененной
        time.sleep(0.001)

        return transaction_data

    async def get_outer_goods(self, remote_transaction: Dict[str, Any]) -> OuterGoodsOrm:
        product_id = remote_transaction['product_id']
        # Выполняем поиск товара/услуги
        for goods in self._outer_goods_list:
            if goods.external_id == product_id:
                return goods

        # Если товар/услуга не найден(а), то создаем его(её)
        fields = dict(
            name=product_id,
            system_id=self.system.id,
            inner_goods_id=None,
        )
        goods = await self.insert(OuterGoodsOrm, **fields)
        self._outer_goods_list.append(goods)

        return goods

    async def issue_virtual_cards(self, amount: int) -> List[str]:
        stmt = sa_select(CardTypeOrm).where(CardTypeOrm.name == "Виртуальная карта")
        card_type_virtual = await self.select_first(stmt)
        dataset = []
        for i in range(amount):
            remote_card = self.api.issue_virtual_card()
            local_card = CardOrm(
                card_number=remote_card['number'],
                card_type_id=card_type_virtual.id,
                external_id=remote_card['id'],
                is_active=False
            )
            await self.save_object(local_card)
            print(f'----- Кол-во выпущенных карт: {i + 1} -----')

        self.logger.info("Все новые виртуальные карты ГПН сохранены в локальную БД")
        card_numbers = [card['card_number'] for card in dataset]
        return card_numbers

    async def delete_card_limits(self, limit_ids: List[str]) -> None:
        for limit_id in limit_ids:
            self.api.delete_card_limit(limit_id=limit_id)

    async def set_card_limits(self, card_external_id: str, limit_ids: List[str]) -> None:
        await self.init_system()

        # Получаем лимиты из БД
        stmt = (
            sa_select(CardLimitOrm)
            .where(CardLimitOrm.id.in_(limit_ids))
        )
        limits: List[CardLimitOrm] = await self.select_all(stmt)

        # В локальной БД, если не указано поле лимита inner_goods_category, это означает, что лимит
        # действует в отношении всех категорий. В ГПН так не работает - категория обязательно должна быть указана.
        new_limits = []
        for limit in limits:
            if limit.inner_goods_category:
                new_limit = {
                    "obj": limit,
                    "inner_goods_category": limit.inner_goods_category,
                    "inner_goods_group_id": limit.inner_goods_group_id,
                    "value": limit.value,
                    "unit": limit.unit,
                    "period": limit.period,
                }
                new_limits.append(new_limit)
            else:
                for category in GoodsCategory:
                    new_limit = {
                        "obj": limit,
                        "inner_goods_category": category,
                        "inner_goods_group_id": limit.inner_goods_group_id,
                        "value": limit.value,
                        "unit": limit.unit,
                        "period": limit.period,
                    }
                    new_limits.append(new_limit)

        # Дополняем записи сведениями об идентификаторах категорий и групп в ГПН
        goods_repository = GoodsRepository(session=self.session, user=None)
        gpn_groups = await goods_repository.get_outer_groups(self.system.id)
        gpn_categories = await goods_repository.get_outer_categories(self.system.id)
        i = 0
        while i < len(new_limits):
            limit = new_limits[i]
            # Получаем идентификатор категории в ГПН
            found = False
            for gpn_category in gpn_categories:
                if limit["inner_goods_category"] == gpn_category.inner_category:
                    found = True
                    limit["gpn_goods_category_id"] = gpn_category.external_id
                    break

            # Если не найдено совпадение, то удаляем запись из списка
            if not found:
                self.logger.error(f"При создании лимита в ГПН не удалось определить идентификатор категории. "
                                  f"Лимит не создан: {limit}")
                new_limits.remove(limit)
                continue

            if limit["inner_goods_group_id"]:
                found = False
                for gpn_group in gpn_groups:
                    if limit["inner_goods_group_id"] == gpn_group.inner_group_id:
                        found = True
                        limit["gpn_goods_group_id"] = gpn_group.external_id

            # Если не найдено совпадение, то удаляем запись из списка
            if not found:
                self.logger.error(f"При создании лимита в ГПН не удалось определить идентификатор категории. "
                                  f"Лимит не создан: {limit}")
                new_limits.remove(limit)
                continue

            # Лимит успешно обработан - увеличиваем счетчик
            i += 1

        # В ГПН создаем лимиты по карте
        for limit in new_limits:
            gpn_limit_id = self.api.set_card_limit(
                card_id=card_external_id,
                goods_category_id=limit["gpn_goods_category_id"],
                goods_group_id=limit.get("gpn_goods_group_id", None),
                value=limit["value"],
                unit=limit["unit"],
                period=limit["period"],
            )
            limit["obj"].external_id = gpn_limit_id
            await self.save_object(limit["obj"])

        # В ГПН изменяем лимиты по группе карт

    async def import_azs(self) -> None:
        await self.init_system()

        # Получаем из ГПН справочник стран
        gpn_countries = self.api.get_countries()

        # Получаем из ГПН справочник регионов
        gpn_regions = self.api.get_regions()

        # Получаем из БД список регионов
        tariff_repository = TariffRepository(session=self.session, user=None)
        regions = await tariff_repository.get_regions()
        local_region_names = [region.name for region in regions]

        # Формируем список новых регионов для записи в БД
        region_dataset = {}
        for region in gpn_regions:
            if region not in local_region_names:
                country_name = ""
                for country in gpn_countries:
                    if country["id"] == region["country_id"]:
                        country_name = country["value"]
                        break

                region_dataset[region["name"]] = country_name

        region_dataset = [{"name": region_name, "country": country} for region_name, country in region_dataset.items()]
        await self.bulk_insert_or_update(RegionOrm, region_dataset, "name")

        # Получаем из БД список регионов
        tariff_repository = TariffRepository(session=self.session, user=None)
        local_regions = await tariff_repository.get_regions()
        local_region_id_by_name = {region.name: region.id for region in local_regions}

        # Получаем из ГПН список АЗС
        stations = self.api.get_stations()

        def get_local_region(region_code: str) -> str | None:
            # Из справочника ГПН получаем имя региона
            region_name = ""
            for gpn_region in gpn_regions:
                if gpn_region["id"] == region_code:
                    region_name = gpn_region["name"]
                    break

            # Из локального справочника получаем ID региона
            return local_region_id_by_name.get(region_name, None)

        def get_own_type(system_own_type: str) -> AzsOwnType:
            if system_own_type.upper() == 'EXT':
                return AzsOwnType.PARTNER
            elif system_own_type.upper() == 'FRAN':
                return AzsOwnType.FRANCHISEE
            elif system_own_type.upper() == 'OPTI':
                return AzsOwnType.OPTI
            else:
                return AzsOwnType.OWN

        def get_working_days(system_working_time: Dict[str, Any] | None) -> str | None:
            return system_working_time if system_working_time else None

        def get_address(system_address: Dict[str, Any] | None) -> str | None:
            return system_address if system_address else None

        def get_coordinate(coordinate: str) -> float:
            if coordinate.startswith("."):
                return float(coordinate[1:])
            else:
                return float(coordinate)

        azs_dataset = [
            {
                "system_id": self.system.id,
                "external_id": azs["siebelId"],
                "name": azs["contractName"],
                "code": azs["contractName"],
                "is_active": True if azs["status"] == "257" else False,
                "region_id": get_local_region(azs["regionCode"]),
                "address": get_address(azs["address"]),
                "own_type": get_own_type(azs["ownType"]),
                "latitude": get_coordinate(azs["latitude"]),
                "longitude": get_coordinate(azs["longitude"]),
                "timezone": azs["timeZone"],
                "working_time": get_working_days(azs["working_time"])
            } for azs in stations
        ]
        await self.bulk_insert_or_update(AzsOrm, azs_dataset, "external_id")

    def get_company_by_card_number(self, card_number: str) -> CompanyOrm | None:
        card = None
        company = None
        for record in self._card_history:
            if record.card.card_number == card_number:
                card = record.card
                company = record.company

        return company if company else card.company

    async def get_azs(self, azs_external_id: str) -> AzsOrm:
        # Выполняем поиск АЗС
        for azs in self._azs_stations:
            if azs.external_id == azs_external_id:
                return azs

        # Если АЗС не найдена, то создаем её
        fields = dict(
            system_id=self.system.id,
            external_id=azs_external_id,
            name=azs_external_id,
            code=azs_external_id,
            is_active=True,
            address={}
        )
        azs = await self.insert(AzsOrm, **fields)
        self._azs_stations.append(azs)

        return azs

    def get_company_tariff_on_transaction_time(self, company: CompanyOrm, transaction_time: datetime,
                                               inner_group: InnerGoodsGroupOrm | None, azs: AzsOrm | None) \
            -> TariffNewOrm:
        # Получаем список тарифов, действовавших для компании на момент совершения транзакции
        tariffs = []
        # print('111111111111111111111111')
        # print(len(self._tariffs))
        for tariff in self._tariffs:
            # print('222222222222222222222222')
            # print(f"policy_id: {tariff.policy_id} | {company.tariff_policy_id} | {tariff.policy_id == company.tariff_policy_id}")
            # print(f"policy_id: {tariff.begin_time} | {transaction_time} | {tariff.begin_time <= transaction_time}")
            # print(f"end_time: {tariff.end_time} | {transaction_time} | {(tariff.end_time and tariff.end_time > transaction_time) or not tariff.end_time}")
            if tariff.policy_id == company.tariff_policy_id and tariff.begin_time <= transaction_time:
                if (tariff.end_time and tariff.end_time > transaction_time) or not tariff.end_time:
                    tariffs.append(tariff)

        # print('33333333333333333333333333')
        # print(f"tariffs length: {len(tariffs)}")
        # Перебираем тарифы и применяем первый подошедший
        for tariff in tariffs:
            # АЗС
            # print(f"azs_id: {tariff.azs_id} | {azs.id} | {tariff.azs_id and tariff.azs_id != azs.id}")
            if tariff.azs_id and tariff.azs_id != azs.id:
                # print('continue')
                continue

            # Тип АЗС
            # print(f"azs_own_type: {tariff.azs_own_type} | {azs.own_type} | "
            #       f"{tariff.azs_own_type and tariff.azs_own_type != azs.own_type}")
            if tariff.azs_own_type and tariff.azs_own_type != azs.own_type:
                # print('continue')
                continue

            # Регион
            # print(f"region_id: {tariff.region_id} | {azs.region_id} | "
            #       f"{tariff.region_id and tariff.region_id != azs.region_id}")
            if tariff.region_id and tariff.region_id != azs.region_id:
                # print('continue')
                continue

            # Группа продуктов
            # print(f"inner_goods_group_id: {tariff.inner_goods_group_id} | {inner_group.id if inner_group else None} | "
            #       f"{tariff.inner_goods_group_id and inner_group and tariff.inner_goods_group_id != inner_group.id}")
            if tariff.inner_goods_group_id and inner_group and tariff.inner_goods_group_id != inner_group.id:
                # print('continue')
                continue

            # Категория продуктов
            # print(f"inner_goods_category: {tariff.inner_goods_category} | "
            #       f"{inner_group.inner_category if inner_group else None}")
            if tariff.inner_goods_category and inner_group and \
                    tariff.inner_goods_category != inner_group.inner_category:
                # print('continue')
                continue

            # Тариф удовлетворяет критериям - возвращаем его
            return tariff

    def remote_card_groups(self) -> List[Dict[str, Any]]:
        if self.card_groups is None:
            self.card_groups = self.api.get_card_groups()

        return self.card_groups

    async def update_group_limits(self, orders: List[GroupLimitOrder]) -> None:
        if not orders:
            return None

        # Получаем из БД организации
        personal_accounts = {order.personal_account for order in orders}
        stmt = (
            sa_select(CompanyOrm)
            .options(
                contains_eager(CompanyOrm.card_groups)
            )
            .join(CardGroupOrm, and_(
                CompanyOrm.id == CardGroupOrm.company_id,
                CardGroupOrm.system_id == self.system.id
            ))
            .where(CompanyOrm.personal_account.in_(personal_accounts))
            .order_by(CompanyOrm.personal_account)
        )
        companies: List[CompanyOrm] = copy.deepcopy(await self.select_all(stmt))

        # Раскидываем организации по ордерам
        for order in orders:
            for company in companies:
                if order.personal_account == company.personal_account:
                    order.company = company
                    companies.remove(company)
                    break

        # Получаем из БД групповые лимиты переданных в функцию организаций
        org = aliased(CompanyOrm, name="org")
        stmt = (
            sa_select(GroupLimitOrm)
            .options(
                joinedload(GroupLimitOrm.company)
            )
            .select_from(GroupLimitOrm, org, SystemOrm)
            .where(SystemOrm.short_name == System.GPN)
            .where(GroupLimitOrm.system_id == SystemOrm.id)
            .where(org.personal_account.in_(personal_accounts))
            .where(GroupLimitOrm.company_id == org.id)
            .order_by(org.personal_account)
        )
        local_group_limits: List[GroupLimitOrm] = copy.deepcopy(await self.select_all(stmt))

        # Раскидываем групповые лимиты по ордерам
        for order in orders:
            i = 0
            while i < len(local_group_limits):
                limit = local_group_limits[i]
                if order.personal_account == limit.company.personal_account:
                    order.local_group_limits.append(limit)
                    local_group_limits.remove(limit)
                elif limit.company.personal_account > order.personal_account:
                    break
                else:
                    i += 1

        # Обрабатываем полученные задания на установку / изменение групповых лимитов
        for order in orders:
            if order.delta_sum:
                """
                Такая комбинация имеет место в следующих случаях:
                - совершены приходные или расходные транзакции в других системах
                - корректировка баланса: пополнение или списание
                - подключен / отключен овердрафт
                - изменен минимальный допустимый баланс организации
                
                Предполагается, что в БД уже существуют записи о групповых лимитах по всем категориям 
                (на момент написания комментария их 6).
                """
                await self.update_group_limits_by_delta_sum(order)

            else:
                """
                Такая комбинация имеет место при установке лимитов по карте сотрудником организации.
                Предполагается, что в БД уже существуют записи о групповых лимитах по всем категориям 
                (на момент написания комментария их 6).
                """
                await self.update_group_limits_by_categories(order)

    async def create_group_limits(self, company_id: str, card_group_external_id: str, available_balance: float) -> None:
        # Получаем идентификатор карточной группы ГПН, сохраненный в БД

        # Создаем лимиты в ГПН на все категории продуктов
        local_limits_dataset = []
        for gpn_category in GpnGoodsCategory:
            limit_sum = available_balance if gpn_category == GpnGoodsCategory.FUEL else 1.0
            limit_sum = int(math.floor(limit_sum))

            if PRODUCTION:
                # Создаем лимит в ГПН
                remote_limit_id = self.api.set_group_limit(
                    limit_id=None,
                    group_id=card_group_external_id,
                    product_category=gpn_category,
                    limit_sum=limit_sum
                )
                # Запоминаем параметры лимита для последующей записи в локальную БД
                local_limits_dataset.append({
                    "system_id": self.system.id,
                    "external_id": remote_limit_id,
                    "company_id": company_id,
                    "limit_sum": limit_sum,
                    "inner_goods_category": gpn_category.value["local_category"]
                })
            else:
                print(f"Псевдо создан лимит на категорию {gpn_category.name} | "
                      f"GROUP_ID: {card_group_external_id} | LIMIT_SUM: {limit_sum}")

        # Записываем созданные лимиты в локальную БД
        if local_limits_dataset:
            await self.bulk_insert_or_update(GroupLimitOrm, local_limits_dataset)

    async def update_group_limits_by_delta_sum(self, order: GroupLimitOrder) -> None:
        # Получаем идентификатор карточной группы ГПН, сохраненный в БД
        group_external_id = order.company.card_groups[0].external_id

        # Из локальной БД получаем все лимиты, которые больше единицы
        limits_to_update = [limit for limit in order.local_group_limits
                            if limit.limit_sum > 1 or limit.inner_goods_category == GoodsCategory.FUEL]

        # Получаем лимит на Топливо
        fuel_limit = None
        for limit in limits_to_update:
            if limit.inner_goods_category == GoodsCategory.FUEL:
                fuel_limit = limit
                break

        # Вычисляем новое значение лимита
        limit_sum = max(int(math.floor(fuel_limit.limit_sum + order.delta_sum)), 1)

        for limit in limits_to_update:
            if PRODUCTION:
                # Обновляем лимит в ГПН
                self.api.set_group_limit(
                    limit_id=limit.external_id,
                    group_id=group_external_id,
                    product_category=GpnGoodsCategory.get_equal_by_local(limit.inner_goods_category),
                    limit_sum=limit_sum
                )
                limit.limit_sum = limit_sum
                await self.save_object(limit)
            else:
                print(f"Псевдо обновлен лимит на категорию {limit.inner_goods_category} | "
                      f"GROUP_ID: {group_external_id} | LIMIT_SUM: {limit_sum}")

    async def update_group_limits_by_categories(self, order: GroupLimitOrder) -> None:
        # Получаем идентификатор карточной группы ГПН, сохраненный в БД
        group_external_id = order.company.card_groups[0].external_id

        # Получаем размер установленного лимита на категорию "Топливо"
        fuel_limit: List[GroupLimitOrm] = filter(
            lambda local_limit: local_limit.inner_goods_category == GoodsCategory.FUEL,
            order.local_group_limits
        )
        fuel_limit: GroupLimitOrm | None = fuel_limit[0] if fuel_limit else None
        limit_sum = int(math.floor(fuel_limit.limit_sum))

        # Если в локальной БД нет записи о групповом лимите на категорию Топливо, то это исключительная ситуация
        if not fuel_limit:
            raise CeleryError(f"В БД не обнаружен групповой лимит на категорию Топливо для организации "
                              f"{order.company.name}, personal_account = {order.company.personal_account}")

        # Сверяем лимиты по категориям, переданным в функцию. Если лимит не равен лимиту на категорию "Топливо",
        # то обновляем его.
        for limit in order.local_group_limits:
            if limit.limit_sum != fuel_limit.limit_sum:
                if PRODUCTION:
                    # Обновляем лимит в ГПН
                    self.api.set_group_limit(
                        limit_id=limit.external_id,
                        group_id=group_external_id,
                        product_category=GpnGoodsCategory.get_equal_by_local(limit.inner_goods_category),
                        limit_sum=limit_sum
                    )
                    limit.limit_sum = limit_sum
                    await self.save_object(limit)

                else:
                    print(f"Псевдо обновлен лимит на категорию {limit.inner_goods_category} | "
                          f"GROUP_ID: {group_external_id} | LIMIT_SUM: {limit_sum}")

    async def create_company(self, company_id: str, personal_account: str, available_balance: float) -> str:
        # Создаем карточную группу в ГПН
        group_id = self.api.create_card_group(personal_account)

        # Создаем карточную группу в БД
        local_card_group = CardGroupOrm(
            system_id=self.system.id,
            external_id=group_id,
            name=personal_account,
            company_id=company_id
        )
        await self.save_object(local_card_group)

        # Создаем групповые лимиты
        await self.create_group_limits(
            company_id=company_id,
            card_group_external_id=group_id,
            available_balance=available_balance
        )

        return group_id

    async def binding_cards(self, card_numbers: List[str], previous_company_id: str, new_company_id: str) -> None:
        """Связывание / открепление карт с карточной группой ГПН. В функцию могут быть переданы карты других систем.
        Предполагается, что все карты привязаны к одной организации (либо не привязаны ни к какой)."""

        # Получаем карты, относящиеся к системе ГПН
        card_repository = CardRepository(session=self.session)
        cards = await card_repository.get_cards_by_filters(system_id=self.system.id, card_numbers=card_numbers)

        company_repository = CompanyRepository(session=self.session)

        # Отвязываем карты ГПН от старой группы
        if previous_company_id and cards:
            # Получаем идентификатор группы карт ГПН
            previous_card_group = await company_repository.get_card_group(
                company_id=previous_company_id,
                system_id=self.system.id
            )

            self.api.unbind_cards_from_group(
                card_numbers=[card.card_number for card in cards],
                card_external_ids=[card.external_id for card in cards],
                group_id=previous_card_group.external_id
            )

        # Привязываем карты к новой группе
        if new_company_id:
            # Получаем идентификатор группы карт ГПН
            card_group = await company_repository.get_card_group(
                company_id=new_company_id,
                system_id=self.system.id
            )

            if card_group:
                group_id = card_group.external_id
            else:
                # Если группа не существует, это означает, что к организации впервые привязали карту ГПН.
                # В этом случае выполняем набор действий по созданию группы и назначению лимитов.
                new_company = await company_repository.get_company(new_company_id)
                available_balance = calc_available_balance(
                    current_balance=new_company.overbought_balance().balance,
                    min_balance=new_company.min_balance,
                    overdraft_on=new_company.overdraft_on,
                    overdraft_sum=new_company.overdraft_sum
                )
                group_id = await self.create_company(
                    company_id=new_company.id,
                    personal_account=new_company.personal_account,
                    available_balance=available_balance
                )

            # Привязываем карты к группе
            self.api.bind_cards_to_group(
                card_numbers=[card.card_number for card in cards],
                card_external_ids=[card.external_id for card in cards],
                group_id=group_id
            )
