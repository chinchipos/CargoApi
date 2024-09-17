import copy
import math
from datetime import datetime
from typing import Dict, Any, List

from sqlalchemy import select as sa_select, delete as sa_delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, selectinload

from src.celery_app.exceptions import CeleryError
from src.celery_app.gpn.api import GPNApi, GpnGoodsCategory
from src.celery_app.group_limit_order import GroupLimitOrder
from src.celery_app.irrelevant_balances import IrrelevantBalances
from src.celery_app.transaction_helper import TransactionHelper
from src.config import TZ, PRODUCTION
from src.database.models import CompanyOrm, CardLimitOrm, AzsOrm, RegionOrm, GroupLimitOrm, CardGroupOrm
from src.database.models.azs import AzsOwnType
from src.database.models.balance_system import BalanceSystemOrm
from src.database.models.card import CardOrm, BlockingCardReason
from src.database.models.card_type import CardTypeOrm
from src.database.models.goods import OuterGoodsOrm
from src.database.models.goods_category import GoodsCategory
from src.database.models.system import CardSystemOrm
from src.database.models.transaction import TransactionOrm
from src.repositories.base import BaseRepository
from src.repositories.card import CardRepository
from src.repositories.company import CompanyRepository
from src.repositories.system import SystemRepository
from src.repositories.tariff import TariffRepository
from src.repositories.transaction import TransactionRepository
from src.utils.common import calc_available_balance
from src.utils.enums import ContractScheme, System
from src.utils.loggers import get_logger


class GPNController(BaseRepository):

    def __init__(self, session: AsyncSession):
        super().__init__(session, None)
        self.logger = get_logger(name="GPNController", filename="celery.log")
        self.api = GPNApi()
        self.system = None
        self._irrelevant_balances = None
        self.card_groups = None
        self.card_types = {}

        self._bst_list: List[BalanceSystemOrm] = []

        self.helper: TransactionHelper | None = None

    async def init_system(self) -> None:
        if not self.system:
            system_repository = SystemRepository(self.session)
            self.system = await system_repository.get_system_by_short_name(
                short_name=System.GPN.value,
                scheme=ContractScheme.OVERBOUGHT
            )
            self._irrelevant_balances = IrrelevantBalances(system_id=self.system.id)
            self.helper = TransactionHelper(session=self.session, logger=self.logger, system_id=self.system.id)

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
        3. Синхронизируем лимиты на группы.
        """

        # ---- 1 ----

        # Получаем список карт от системы ГПН
        remote_cards = self.api.get_gpn_cards()
        self.logger.info(f"Количество карт в API ГПН: {len(remote_cards)}")

        # Синхронизируем группы карт
        self.logger.info("Запускаю синхронизацию карточных групп")
        await self.sync_card_groups(remote_cards)
        self.logger.info("Синхронизация карточных групп завершена")

        # ---- 2 ----

        # Синхронизируем карты
        self.logger.info("Запускаю синхронизацию карт")
        await self.sync_cards(remote_cards)
        self.logger.info("Синхронизация лимитов завершена")

        # ---- 3 ----
        # Устанавливаем лимиты на группы
        self.logger.info("Запускаю синхронизацию лимитов на группы карт")
        await self.sync_group_limits()
        self.logger.info("Синхронизация лимитов завершена")

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
                    if not company.has_card_group(System.GPN):
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
        local_cards = await self.helper.get_local_cards()
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
        local_cards = await self.helper.get_local_cards()
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
            if gpn_card['group_id']:
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
            .where(CompanyOrm.personal_account == "5850627")
            .where(CompanyOrm.id == CardOrm.company_id)
            .where(CardOrm.id == CardSystemOrm.card_id)
            .where(CardSystemOrm.system_id == self.system.id)
        )
        companies = await self.select_all(stmt)

        def remote_limit_exists(limit_external_id: str, _remote_group_limits: List[Dict[str, Any]]) -> bool:
            for _remote_limit in _remote_group_limits:
                if _remote_limit["id"] == limit_external_id:
                    return True

            return False

        def get_remote_limit(limit_external_id: str, _remote_group_limits: List[Dict[str, Any]]) -> Dict[str, Any]:
            for _remote_limit in _remote_group_limits:
                if _remote_limit["id"] == limit_external_id:
                    return _remote_limit

        def count_remote_limits_by_category(_gpn_category: GpnGoodsCategory,
                                            _remote_group_limits: List[Dict[str, Any]]) -> int:
            i = 0
            for _remote_limit in _remote_group_limits:
                if _remote_limit["productType"] == _gpn_category.value["id"]:
                    i += 1

            return i

        def delete_remote_limits_by_category(group_external_id: str, _gpn_category: GpnGoodsCategory,
                                             _remote_group_limits: List[Dict[str, Any]],
                                             excluded_limit_external_id: str | None = None) -> None:
            for _remote_limit in _remote_group_limits:
                if _remote_limit["productType"] == _gpn_category.value["id"] \
                        and _remote_limit["id"] != excluded_limit_external_id:
                    self.api.delete_group_limit(limit_id=_remote_limit["id"], group_id=group_external_id)

        async def create_limit_locally_and_remotely(_gpn_category: GpnGoodsCategory, _company: CompanyOrm):

            # Получаем доступный баланс организации
            available_balance = calc_available_balance(
                current_balance=_company.overbought_balance().balance,
                min_balance=_company.min_balance,
                overdraft_on=_company.overdraft_on,
                overdraft_sum=_company.overdraft_sum
            )

            # Устанавливаем размер лимита. На следующем этапе он может быть изменен. Пока пусть будет такой.
            limit_sum = max(int(math.floor(available_balance)), 1) if _gpn_category == GpnGoodsCategory.FUEL else 1

            # Создаем лимит в ГПН
            remote_limit_id = self.api.set_group_limit(
                limit_id=None,
                group_id=group.external_id,
                product_category=_gpn_category,
                limit_sum=limit_sum
            )
            if not remote_limit_id:
                raise CeleryError("Не удалось создать групповой лимит ГПН")

            # Записываем лимит в локальную БД
            limit_dataset = {
                "system_id": self.system.id,
                "external_id": remote_limit_id,
                "company_id": _company.id,
                "limit_sum": limit_sum,
                "inner_goods_category": _gpn_category.value["local_category"]
            }
            await self.insert(GroupLimitOrm, **limit_dataset)
            self.logger.info(f"Создан и записан в БД групповой лимит {_company.name} {limit_sum} р. на "
                             f"категорию {_gpn_category.value['local_category']}")

        # Сверяем наличие групповых лимитов локально и в ГПН. Суммы лимитов будут сверяться на следующем этапе.
        for company in companies:
            # Из ГПН получаем лимиты по группе карт
            group: CardGroupOrm = company.get_card_group(System.GPN)
            remote_group_limits = self.api.get_card_group_limits(group.external_id)

            # Оцениваем соответствие лимитов по каждой категории продуктов.
            for gpn_category in GpnGoodsCategory:
                # Если локально лимит не найден, то создаем его локально и пересоздаем в ГПН.
                # Если локально найдено несколько лимитов, то удаляем лимиты локально,
                # удаляем их в ГПН и создаем заново в обеих локациях.
                found_locally = False
                limits_count = 0
                found_limit_ids = []
                founded_local_limit = None
                for local_limit in company.group_limits:
                    if local_limit.system_id == self.system.id \
                            and local_limit.inner_goods_category == gpn_category.value["local_category"]:
                        found_locally = True
                        founded_local_limit = local_limit
                        found_limit_ids.append(local_limit.id)
                        limits_count += 1

                if not found_locally or limits_count > 1:
                    # Удаляем из БД найденные лимиты
                    for limit_id in found_limit_ids:
                        await self.delete_object(GroupLimitOrm, limit_id)

                    # Удаляем соответствующие лимиты из ГПН
                    delete_remote_limits_by_category(
                        group_external_id=group.external_id,
                        _gpn_category=gpn_category,
                        _remote_group_limits=remote_group_limits
                    )

                    # Создаем лимит в обеих локациях
                    await create_limit_locally_and_remotely(
                        _gpn_category=gpn_category,
                        _company=company
                    )

                else:
                    # Локально лимит присутствует в единственном количестве, как и должно быть.
                    # Если в ГПН не найден, то удаляем локально и создаем заново
                    if not remote_limit_exists(founded_local_limit.external_id, remote_group_limits):
                        # Удаляем локально
                        await self.delete_object(GroupLimitOrm, founded_local_limit.id)

                        # Создаем лимит в обеих локациях
                        await create_limit_locally_and_remotely(
                            _gpn_category=gpn_category,
                            _company=company
                        )
                    else:
                        remote_limits_amount = count_remote_limits_by_category(
                            _gpn_category=gpn_category,
                            _remote_group_limits=remote_group_limits
                        )
                        if remote_limits_amount > 1:
                            delete_remote_limits_by_category(
                                group_external_id=group.external_id,
                                _gpn_category=gpn_category,
                                _remote_group_limits=remote_group_limits,
                                excluded_limit_external_id=founded_local_limit.external_id
                            )

        # Сверяем суммы лимитов.
        # На данном этапе мы знаем, что шести лимитам локальным соответствует шесть лимитов в ГПН.

        # Получаем из БД информацию у каких организаций какие карточные лимиты установлены
        stmt = (
            sa_select(CompanyOrm.personal_account, CardLimitOrm.inner_goods_category)
            .select_from(CompanyOrm, CardOrm, CardLimitOrm)
            .where(CardOrm.id == CardLimitOrm.card_id)
            .where(CardLimitOrm.system_id == self.system.id)
            .where(CompanyOrm.id == CardOrm.company_id)
            .order_by(CompanyOrm.personal_account)
            .distinct()
        )
        company_limit_dataset = await self.select_all(stmt, scalars=False)
        company_limit_dict = {}
        for data in company_limit_dataset:
            if data[0] in company_limit_dict:
                company_limit_dict[data[0]].append(data[1])
            else:
                company_limit_dict[data[0]] = [data[1]]

        companies = await self.select_all(stmt)
        for company in companies:
            group: CardGroupOrm = company.get_card_group(System.GPN)
            remote_group_limits = self.api.get_card_group_limits(group.external_id)

            # Получаем доступный баланс организации
            available_balance = calc_available_balance(
                current_balance=company.overbought_balance().balance,
                min_balance=company.min_balance,
                overdraft_on=company.overdraft_on,
                overdraft_sum=company.overdraft_sum
            )
            limit_sum = max(math.floor(available_balance), 0)

            for local_group_limit in company.group_limits:
                remote_group_limit = get_remote_limit(
                    limit_external_id=local_group_limit.external_id,
                    _remote_group_limits=remote_group_limits
                )
                local_group_limit.limit_sum

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
                discount_fee_sum = local_transaction.discount_sum if local_transaction.discount_sum else \
                    local_transaction.fee_sum
                if personal_account in self._irrelevant_balances.total_sum_deltas:
                    self._irrelevant_balances.total_sum_deltas[personal_account] -= local_transaction.total_sum
                    self._irrelevant_balances.discount_fee_sum_deltas[personal_account] -= discount_fee_sum
                else:
                    self._irrelevant_balances.total_sum_deltas[personal_account] = local_transaction.total_sum
                    self._irrelevant_balances.discount_fee_sum_deltas[personal_account] = discount_fee_sum

        # Удаляем помеченные транзакции из БД
        # self.logger.info(f'Удалить транзакции ГПН из локальной БД: {len(to_delete_local)} шт')
        # if to_delete_local:
        #     for transaction in to_delete_local:
        #         await self.delete_object(TransactionOrm, transaction.id)

        # Сообщаем о транзакциях, которые есть в БД, но нет в системе поставщика
        if to_delete_local:
            self.logger.error("В локальной БД присутствуют транзакции, "
                              f"которых нет в {self.system.short_name}: {to_delete_local}")

        # Транзакции от системы, оставшиеся необработанными, записываем в локальную БД.
        self.logger.info(f'Новые транзакции ГПН: {len(remote_transactions)} шт')
        if remote_transactions:
            await self.process_new_remote_transactions(remote_transactions)

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

    async def process_new_remote_transactions(self, remote_transactions: List[Dict[str, Any]]) -> None:
        # Сортируем транзакции по времени совершения
        def sorting(tr):
            return tr['timestamp']

        remote_transactions = sorted(remote_transactions, key=sorting)

        # Подготавливаем список транзакций для сохранения в БД
        transactions_to_save = []
        for remote_transaction in remote_transactions:
            transaction_data = await self.process_new_remote_transaction(remote_transaction=remote_transaction)
            if transaction_data:
                transactions_to_save.append(transaction_data)
                # if transaction_data['balance_id']:
                self._irrelevant_balances.add(
                    balance_id=str(transaction_data['balance_id']),
                    irrelevancy_date_time=transaction_data['date_time_load']
                )

        # Сохраняем транзакции в БД
        await self.bulk_insert_or_update(TransactionOrm, transactions_to_save)

    async def process_new_remote_transaction(self, remote_transaction: Dict[str, Any]) \
            -> Dict[str, Any] | None:
        """
        Обработка транзакции, сохранение в БД. Примеры транзакций см. в файле transaction_examples.txt
        """
        """
        purchase = True if remote_transaction['type'] == "P" else False
        comments = ''

        # Получаем карту
        card = self.helper.get_local_card(card_number, self._local_cards)

        # Получаем баланс
        company = await self.helper.get_card_company(card=card)
        balance = company.overbought_balance()
        """

        # Получаем продукт
        outer_goods = await self.get_outer_goods(goods_external_id=remote_transaction['product_id'])

        # Получаем АЗС
        azs = await self.get_azs(azs_external_id=remote_transaction['poi_id'])

        """
        # Получаем тариф
        ## tariff = await self.helper.get_company_tariff_on_transaction_time(
        ##     company=company,
        ##     transaction_time=remote_transaction['timestamp'],
        ##     inner_group=outer_goods.outer_group.inner_group if outer_goods.outer_group else None,
        ##     azs=azs,
        ##     system_id=self.system.id
        ## )
        ## if not tariff:
        ##     self.logger.error(f"Не удалось определить тариф для транзакции {remote_transaction}")

        # Сумма транзакции
        ## transaction_type = TransactionType.PURCHASE if purchase else TransactionType.REFUND
        ## transaction_sum = -abs(remote_transaction['sum_no_discount']) if purchase \
        ##     else abs(remote_transaction['sum_no_discount'])

        # Сумма скидки/наценки
        ## discount_fee_percent = tariff.discount_fee / 100 if tariff else 0
        ## discount_fee_sum = transaction_sum * discount_fee_percent

        # Получаем итоговую сумму
        ## total_sum = transaction_sum + discount_fee_sum
        """

        transaction_data = await self.helper.process_new_remote_transaction(
            card_number=remote_transaction['card_number'],
            outer_goods=outer_goods,
            azs=azs,
            irrelevant_balances=self._irrelevant_balances,
            purchase=True if remote_transaction['type'] == "P" else False,
            comments='',
            system_id=self.system.id,
            transaction_external_id=str(remote_transaction['id']),
            transaction_time=remote_transaction['timestamp'],
            transaction_sum=remote_transaction['sum_no_discount'],
            transaction_fuel_volume=remote_transaction['qty'],
            transaction_price=remote_transaction['price_no_discount']
        )
        """
        ## transaction_data = dict(
        ##     external_id=str(remote_transaction['id']),
        ##     date_time=remote_transaction['timestamp'],
        ##     date_time_load=datetime.now(tz=TZ),
        ##     transaction_type=transaction_type,
        ##     system_id=self.system.id,
        ##     card_id=card.id,
        ##     balance_id=balance.id,
        ##     azs_code=remote_transaction['poi_id'],
        ##     outer_goods_id=outer_goods.id if outer_goods else None,
        ##     fuel_volume=-remote_transaction['qty'],
        ##     price=remote_transaction['price_no_discount'],
        ##     transaction_sum=transaction_sum,
        ##     tariff_new_id=tariff.id if tariff else None,
        ##     discount_sum=discount_fee_sum if discount_fee_percent < 0 else 0,
        ##     fee_sum=discount_fee_sum if discount_fee_percent > 0 else 0,
        ##     total_sum=total_sum,
        ##     company_balance_after=0,
        ##     comments=comments,
        ## )

        # Вычисляем дельту изменения суммы баланса - понадобится позже для правильного
        # выставления лимита на группу карт
        ## if company.personal_account in self._irrelevant_balances.total_sum_deltas:
        ##     self._irrelevant_balances.total_sum_deltas[company.personal_account] += transaction_data["total_sum"]
        ##     self._irrelevant_balances.discount_fee_sum_deltas[company.personal_account] += discount_fee_sum
        ## else:
        ##     self._irrelevant_balances.total_sum_deltas[company.personal_account] = transaction_data["total_sum"]
        ##     self._irrelevant_balances.discount_fee_sum_deltas[company.personal_account] = discount_fee_sum

        # Это нужно, чтобы в БД у транзакций отличалось время и можно было корректно выбрать транзакцию,
        # которая предшествовала измененной
        ## time.sleep(0.001)
        """
        return transaction_data

    async def get_outer_goods(self, goods_external_id: str) -> OuterGoodsOrm:
        outer_goods = await self.helper.get_outer_goods_item(goods_external_id=goods_external_id)
        if not outer_goods:
            # Если продукт не найден, то создаем его
            outer_goods_data = dict(
                external_id=goods_external_id,
                name=goods_external_id,
                system_id=self.system.id,
                inner_goods_id=None,
            )
            outer_goods = await self.insert(OuterGoodsOrm, **outer_goods_data)

        return outer_goods

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

        # Удаление лимитов из БД в норме выполняется перед удалением из системы.
        # На данном этапе их уже не должно быть в БД. Но на всякий случай выполним "пустое" удаление.
        # Вдруг предшествующий код изменится в будущем.
        stmt = sa_delete(CardLimitOrm).where(CardLimitOrm.external_id.in_(limit_ids))
        await self.session.execute(stmt)
        await self.session.commit()

    async def set_card_limits(self, company_id: str, card_external_id: str, limit_ids: List[str]) -> None:
        await self.init_system()

        # Получаем лимиты из БД
        stmt = (
            sa_select(CardLimitOrm)
            .where(CardLimitOrm.id.in_(limit_ids))
        )
        limits: List[CardLimitOrm] = await self.select_all(stmt)

        # В локальной БД, если не указано поле лимита inner_goods_category, это означает, что лимит
        # действует в отношении всех категорий. В ГПН так не работает - категория обязательно должна быть указана.
        # new_limits = []
        # for limit in limits:
        #     if limit.inner_goods_category:
        #         new_limit = {
        #             "obj": limit,
        #             "inner_goods_category": limit.inner_goods_category,
        #             "inner_goods_group_id": limit.inner_goods_group_id,
        #             "value": limit.value,
        #             "unit": limit.unit,
        #             "period": limit.period,
        #         }
        #         new_limits.append(new_limit)
        #     else:
        #         for category in GoodsCategory:
        #             new_limit = {
        #                 "obj": limit,
        #                 "inner_goods_category": category,
        #                 "inner_goods_group_id": limit.inner_goods_group_id,
        #                 "value": limit.value,
        #                 "unit": limit.unit,
        #                 "period": limit.period,
        #             }
        #             new_limits.append(new_limit)

        # Дополняем записи сведениями об идентификаторах категорий и групп в ГПН
        # oods_repository = GoodsRepository(session=self.session, user=None)
        # pn_groups = await goods_repository.get_outer_groups(self.system.id)
        # ategories = await goods_repository.get_outer_categories(self.system.id)
        #  = 0
        # hile i < len(new_limits):
        #    limit = new_limits[i]
        #    # Получаем идентификатор категории в ГПН
        #    found = False
        #    for category in categories:
        #        if limit["inner_goods_category"] == category.inner_category:
        #            found = True
        #            gpn_goods_category = GpnGoodsCategory.get_equal_by_local(category.inner_category)
        #            limit["gpn_goods_category_id"] = gpn_goods_category.value["id"]
        #            break

        #    # Если не найдено совпадение, то удаляем запись из списка
        #    if not found:
        #        self.logger.error(f"При создании лимита в ГПН не удалось определить идентификатор категории. "
        #                          f"Лимит не создан в ГПН: {limit}")
        #        new_limits.remove(limit)
        #        continue

        #    if limit["inner_goods_group_id"]:
        #        found = False
        #        for gpn_group in gpn_groups:
        #            if limit["inner_goods_group_id"] == gpn_group.inner_group_id:
        #                found = True
        #                limit["gpn_goods_group_id"] = gpn_group.external_id

        #    # Если не найдено совпадение, то удаляем запись из списка
        #    if not found:
        #        self.logger.error(f"При создании лимита в ГПН не удалось определить идентификатор категории. "
        #                          f"Лимит не создан в ГПН: {limit}")
        #        new_limits.remove(limit)
        #        continue

        #    # Лимит успешно обработан - увеличиваем счетчик
        #    i += 1

        # print('YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY')
        # print(limits)

        # В ГПН создаем лимиты по карте
        for limit in limits:
            gpn_goods_group_id = None
            if limit.inner_goods_group:
                gpn_goods_group = limit.inner_goods_group.get_outer_goods_group(self.system.id)
                gpn_goods_group_id = gpn_goods_group.id

            gpn_limit_id = self.api.set_card_limit(
                card_id=card_external_id,
                gpn_goods_category=GpnGoodsCategory.get_equal_by_local(limit.inner_goods_category),
                goods_group_id=gpn_goods_group_id,
                value=limit.value,
                unit=limit.unit,
                period=limit.period,
            )
            limit.external_id = gpn_limit_id
            await self.save_object(limit)

            # Обновляем групповой лимит ГПН
            await self.update_group_limit_by_card_limit(
                company_id=company_id,
                card_limit_goods_category=limit.inner_goods_category
            )

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

    async def get_azs(self, azs_external_id: str) -> AzsOrm:
        azs = await self.helper.get_azs(azs_external_id=azs_external_id)
        if azs:
            return azs

        # Если АЗС не найдена, то создаем её
        azs_fields = dict(
            system_id=self.system.id,
            external_id=azs_external_id,
            name=azs_external_id,
            is_active=True,
            address={}
        )
        azs = await self.insert(AzsOrm, **azs_fields)
        return azs

    def remote_card_groups(self) -> List[Dict[str, Any]]:
        if self.card_groups is None:
            self.card_groups = self.api.get_card_groups()

        return self.card_groups

    async def update_group_limits(self, orders: List[Dict[str, Any]]) -> None:
        if not orders:
            return None

        orders = [
            GroupLimitOrder(
                personal_account=order["personal_account"],
                delta_sum=order["delta_sum"]
            ) for order in orders
        ]
        # Получаем из БД организации, у которых есть карты ГПН
        personal_accounts = {order.personal_account for order in orders}
        stmt = (
            sa_select(CompanyOrm)
            .options(
                contains_eager(CompanyOrm.card_groups)
            )
            .options(
                selectinload(CompanyOrm.group_limits)
            )
            .outerjoin(CardGroupOrm, and_(
                CompanyOrm.id == CardGroupOrm.company_id,
                CardGroupOrm.system_id == self.system.id
            ))
            .where(CompanyOrm.personal_account.in_(personal_accounts))
            .where(CardOrm.company_id == CompanyOrm.id)
            .where(CardSystemOrm.card_id == CardOrm.id)
            .where(CardSystemOrm.system_id == self.system.id)
            .order_by(CompanyOrm.personal_account)
        )
        self.statement(stmt)
        companies: List[CompanyOrm] = copy.deepcopy(await self.select_all(stmt))
        if not companies:
            self.logger.warning("Пустой список организаций, работающих с системой ГПН. "
                                "Обновление карточных лимитов ГПН не требуется.")
            return None

        # Раскидываем организации по ордерам
        for order in orders:
            for company in companies:
                if order.personal_account == company.personal_account:
                    if not company.card_groups:
                        raise CeleryError("Не удалось определить карточную группу ГПН для организации "
                                          f"{company.name} {company.personal_account}")
                    order.company = company
                    companies.remove(company)
                    break

            if not order.company:
                raise CeleryError(f"Не удалось определить организацию по лицевому счету {order.personal_account}")

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

    async def create_group_limits(self, company_id: str, card_group_external_id: str, available_balance: float) -> None:
        # Получаем идентификатор карточной группы ГПН, сохраненный в БД

        # Создаем лимиты в ГПН на все категории продуктов
        local_limits_dataset = []
        for gpn_category in GpnGoodsCategory:
            limit_sum = max(int(math.floor(available_balance)), 1) if gpn_category == GpnGoodsCategory.FUEL else 1

            # Создаем лимит в ГПН
            remote_limit_id = self.api.set_group_limit(
                limit_id=None,
                group_id=card_group_external_id,
                product_category=gpn_category,
                limit_sum=limit_sum
            )
            if not remote_limit_id:
                raise CeleryError("Не удалось создать групповой лимит ГПН")

            # Запоминаем параметры лимита для последующей записи в локальную БД
            local_limits_dataset.append({
                "system_id": self.system.id,
                "external_id": remote_limit_id,
                "company_id": company_id,
                "limit_sum": limit_sum,
                "inner_goods_category": gpn_category.value["local_category"]
            })

        # Записываем созданные лимиты в локальную БД
        if local_limits_dataset:
            await self.bulk_insert_or_update(GroupLimitOrm, local_limits_dataset)

    async def update_group_limits_by_delta_sum(self, order: GroupLimitOrder) -> None:
        # Получаем идентификатор карточной группы ГПН, сохраненный в БД
        group_external_id = order.company.card_groups[0].external_id

        # Из локальной БД получаем все лимиты, которые больше единицы
        limits_to_update = [limit for limit in order.company.group_limits
                            if limit.limit_sum > 1 or limit.inner_goods_category == GoodsCategory.FUEL]

        # Получаем лимит на Топливо
        fuel_limit = None
        for limit in limits_to_update:
            if limit.inner_goods_category == GoodsCategory.FUEL:
                fuel_limit = limit
                break

        # Вычисляем новое значение лимита
        fuel_limit_sum = fuel_limit.limit_sum if fuel_limit.limit_sum > 1 else 0
        limit_sum = max(int(math.floor(fuel_limit_sum + order.delta_sum)), 1)

        for limit in limits_to_update:
            limit.limit_sum = limit_sum

            # Обновляем лимит в ГПН
            limit_external_id = self.api.set_group_limit(
                limit_id=limit.external_id,
                group_id=group_external_id,
                product_category=GpnGoodsCategory.get_equal_by_local(limit.inner_goods_category),
                limit_sum=limit_sum
            )
            if not limit_external_id:
                # Пробуем пересоздать лимит
                limit_external_id = self.api.set_group_limit(
                    limit_id=None,
                    group_id=group_external_id,
                    product_category=GpnGoodsCategory.get_equal_by_local(limit.inner_goods_category),
                    limit_sum=limit_sum
                )
                if not limit_external_id:
                    await self.save_object(limit)
                    raise CeleryError("Не удалось установить лимит ГПН")

                limit.external_id = limit_external_id

            await self.save_object(limit)

    async def update_group_limit_by_card_limit(self, company_id: str, card_limit_goods_category: GoodsCategory) \
            -> None:
        # Получаем организацию
        company_repository = CompanyRepository(session=self.session)
        company = await company_repository.get_company(company_id)

        # Получаем идентификатор карточной группы ГПН
        group = company.get_card_group(System.GPN)

        # Получаем размер установленного группового лимита на категорию "Топливо"
        group_fuel_limit: List[GroupLimitOrm] = list(filter(
            lambda local_limit: local_limit.inner_goods_category == GoodsCategory.FUEL,
            company.group_limits
        ))
        group_fuel_limit: GroupLimitOrm | None = group_fuel_limit[0] if group_fuel_limit else None

        # Если в локальной БД нет записи о групповом лимите на категорию Топливо, то это исключительная ситуация
        if not group_fuel_limit:
            raise CeleryError(f"В БД не обнаружен групповой лимит на категорию Топливо для организации "
                              f"{company.name}, personal_account = {company.personal_account}")

        # Сверяем лимиты по категориям, переданным в функцию. Если лимит не равен лимиту на категорию "Топливо",
        # то обновляем его.
        for limit in company.group_limits:
            if limit.inner_goods_category == card_limit_goods_category \
                    and limit.limit_sum != group_fuel_limit.limit_sum:

                limit.limit_sum = group_fuel_limit.limit_sum

                # Обновляем лимит в ГПН
                limit_external_id = self.api.set_group_limit(
                    limit_id=limit.external_id,
                    group_id=group.external_id,
                    product_category=GpnGoodsCategory.get_equal_by_local(limit.inner_goods_category),
                    limit_sum=group_fuel_limit.limit_sum
                )
                if not limit_external_id:
                    # Пробуем пересоздать лимит
                    limit_external_id = self.api.set_group_limit(
                        limit_id=None,
                        group_id=group.external_id,
                        product_category=GpnGoodsCategory.get_equal_by_local(limit.inner_goods_category),
                        limit_sum=group_fuel_limit.limit_sum
                    )
                    if not limit_external_id:
                        await self.save_object(limit)
                        raise CeleryError("Не удалось установить лимит ГПН")

                    limit.external_id = limit_external_id

                await self.save_object(limit)
                self.logger.info(f"В БД по организации {company.name} {company.personal_account} установлен "
                                 f"лимит {limit.limit_sum} р. на категорию {limit.inner_goods_category.name}")

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
        previous_company = await company_repository.get_company(previous_company_id)
        new_company = await company_repository.get_company(new_company_id)

        # Отвязываем карты ГПН от старой группы
        if previous_company_id and cards:
            # Получаем идентификатор группы карт ГПН
            previous_card_group = await previous_company.get_card_group(System.GPN)
            if previous_card_group:
                self.api.unbind_cards_from_group(
                    card_numbers=[card.card_number for card in cards],
                    card_external_ids=[card.external_id for card in cards],
                    group_id=previous_card_group.external_id
                )

        # Привязываем карты к новой группе
        if new_company_id:
            # Получаем идентификатор группы карт ГПН
            new_card_group = await new_company.get_card_group(System.GPN)

            if new_card_group:
                group_id = new_card_group.external_id
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
