import time
from datetime import datetime
from typing import Dict, Any, List

from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, aliased

from src.celery_app.gpn.api import GPNApi, ProductCategory
from src.celery_app.gpn.config import SYSTEM_SHORT_NAME
from src.celery_app.irrelevant_balances import IrrelevantBalances
from src.celery_app.transaction_helper import get_local_cards, get_local_card, get_tariff_on_date_by_balance, \
    get_current_tariff_by_balance
from src.config import TZ, PRODUCTION
from src.database.model import CompanyOrm
from src.database.model.card import CardOrm, BlockingCardReason
from src.database.model.card_type import CardTypeOrm
from src.database.model.models import (CardSystem as CardSystemOrm, Transaction as TransactionOrm,
                                       BalanceTariffHistory as BalanceTariffHistoryOrm,
                                       BalanceSystemTariff as BalanceSystemTariffOrm)
from src.database.model.balance import BalanceOrm as BalanceOrm
from src.database.model.goods import OuterGoodsOrm
from src.repositories.base import BaseRepository
from src.repositories.card import CardRepository
from src.repositories.system import SystemRepository
from src.repositories.transaction import TransactionRepository
from src.utils.common import calc_available_balance
from src.utils.enums import ContractScheme, TransactionType
from src.utils.loggers import get_logger


class GPNController(BaseRepository):

    def __init__(self, session: AsyncSession):
        super().__init__(session, None)
        self.logger = get_logger(name="GPNController", filename="celery.log")
        self.api = GPNApi()
        self.system = None
        self._irrelevant_balances = IrrelevantBalances()
        self.card_groups = []
        self.card_types = {}

        self._local_cards: List[CardOrm] = []
        self._balance_card_relations: Dict[str, str] = {}
        self._tariffs_history: List[BalanceTariffHistoryOrm] = []
        self._bst_list: List[BalanceSystemTariffOrm] = []
        self._outer_goods_list: List[OuterGoodsOrm] = []

    async def init_system(self) -> None:
        if not self.system:
            system_repository = SystemRepository(self.session)
            self.system = await system_repository.get_system_by_short_name(
                system_fhort_name=SYSTEM_SHORT_NAME,
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

    async def sync_cards(self) -> None:
        """
        1. Сравниваем номера карт и создаем или удаляем карты в локальной БД без присвоения групп.
        2. Сравниваем группы карт и создаем или удаляем группы в ГПН.
        3. Устанавливаем лимиты на группы.
        4. Сверяем в правильных ли группах находятся карты и в ГПН разносим карты по группам в соответствии с
        принадлежностью карт в локальной БД
        """
        await self.init_system()
        # ---- 1 ----
        # Получаем список карт от системы ГПН
        remote_cards = self.api.get_gpn_cards()
        self.logger.info(f"Количество карт в API ГПН: {len(remote_cards)}")

        # Получаем типы карт
        await self.get_card_types(remote_cards)

        # Получаем список карт из локальной БД, привязанных к ГПН
        local_cards = await get_local_cards(session=self.session, system_id=self.system.id)
        self.logger.info(f"Количество карт в локальной БД (до синхронизации): {len(local_cards)}")

        # Создаем в локальной БД новые карты и привязываем их к ГПН - статус карты из ГПН транслируем на локальную БД.
        # Привязываем в локальной БД карты, открепленные от ГПН - статус не устанавливаем.
        local_card_numbers = [local_card.card_number for local_card in local_cards]
        for remote_card in remote_cards:
            if remote_card['number'] not in local_card_numbers:
                is_active = True if "locked" not in remote_card["status"].lower() else False
                await self.process_unbinded_local_card_or_create_new(
                    external_id=remote_card['id'],
                    card_number=remote_card['number'],
                    card_type_name=remote_card["carrier_name"],
                    is_active=is_active
                )

        # Локальным картам присваиваем external_id, если не присвоено
        dataset = []
        for local_card in local_cards:
            for remote_card in remote_cards:
                if remote_card['number'] == local_card.card_number:
                    if remote_card['id'] != local_card.external_id:
                        dataset.append({"id": local_card.id, "external_id": remote_card['id']})

        if dataset:
            await self.bulk_update(CardOrm, dataset)

        # ---- 2 ----
        # Синхронизируем сами группы карт
        await self.sync_card_groups(remote_cards)

        # ---- 3 ----
        # Устанавливаем лимиты на группы
        self.logger.info("Запускаю синхронизацию лимитов на группы карт")
        await self.set_group_limits_by_balance_ids(balance_ids=None, force=True)

        # ---- 4 ----
        self.logger.info("Запускаю проверку соответствия карт группам")
        # Из локальной БД получаем список карт, привязанных к ГПН
        local_cards = await get_local_cards(
            session=self.session,
            system_id=self.system.id
        )
        self.logger.info(f"Количество карт в локальной БД (после синхронизации): {len(local_cards)}")

        # Из API получаем список групп карт
        gpn_card_groups = self.api.get_card_groups()
        gpn_group_id_by_name = {gpn_card_group['name']: gpn_card_group['id'] for gpn_card_group in gpn_card_groups}

        # Сравниваем ЛС организаций, которым принадлежат карты с группами ГПН.
        # Записи в локальной БД имеют первичное значение.

        # Открепляем от групп карты, которые в них не должны состоять
        gpn_cards_dict = {card['number']: card for card in remote_cards}
        cards_without_company_external_ids = []
        for local_card in local_cards:
            gpn_card = gpn_cards_dict[local_card.card_number]
            if not local_card.company_id or \
                    gpn_card['group_id'] != gpn_group_id_by_name[local_card.company.personal_account]:
                cards_without_company_external_ids.append(gpn_card['id'])

        if cards_without_company_external_ids:
            self.api.unbind_cards_from_group(
                card_external_ids=cards_without_company_external_ids,
                remote_cards=remote_cards
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
            self.api.bind_cards_to_group(card_external_ids=card_external_ids, group_id=group_id)

        # Записываем в БД время последней успешной синхронизации
        await self.update_object(self.system, update_data={"cards_sync_dt": datetime.now(tz=TZ)})
        self.logger.info('Синхронизация карт выполнена')

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
            .select_from(CompanyOrm, CardOrm, CardSystemOrm)
            .where(CompanyOrm.id == CardOrm.company_id)
            .where(CardOrm.id == CardSystemOrm.card_id)
            .where(CardSystemOrm.system_id == self.system.id)
        )
        companies = await self.select_all(stmt)

        # Из API получаем список групп карт
        groups = self.api.get_card_groups()

        # Сравниваем непосредственно группы карт.
        # Совпадающие группы убираем из списков для уменьшения стоимости алгоритма.
        i = 0
        while i < len(companies):
            company = companies[i]
            personal_account = company.personal_account
            found = False
            for gpn_group in groups:
                if gpn_group['name'] == personal_account:
                    # Найдена совпадающая группа
                    found = True
                    companies.remove(company)
                    groups.remove(gpn_group)
                    break

            if not found:
                # Совпадающая группа НЕ найдена, переходим к следующей.
                i += 1

        if PRODUCTION:
            # Удаляем в API избыточные группы.
            for group in groups:
                # Открепляем карты от группы
                card_external_ids = [card['id'] for card in remote_cards if card['group_id'] == group['id']]
                self.api.unbind_cards_from_group(
                    card_external_ids=card_external_ids,
                    remote_cards=remote_cards
                )

                # Удаляем группу
                self.api.delete_gpn_group(group_id=group['id'], group_name=group['name'])

            # Создаем в API недостающие группы.
            for company in companies:
                self.api.create_card_group(company.personal_account)

    async def process_unbinded_local_card_or_create_new(self, external_id: str, card_number: str, card_type_name: str,
                                                        is_active: bool) -> None:
        stmt = sa_select(CardOrm).where(CardOrm.card_number == card_number)
        card = await self.select_first(stmt)
        if card:
            # Карта существует, но она не привязана к ГПН. Привязываем её.
            card_system_date = {"card_id": card.id, "system_id": self.system.id}
            await self.insert(CardSystemOrm, **card_system_date)

            self.logger.info(f"{card_number} | существующая в БД карта привязана к ГПН")

        else:
            # Карта не существует в локальной БД. Создаем её.
            new_card_data = {
                "external_id": external_id,
                "card_number": card_number,
                "card_type_id": self.card_types[card_type_name].id,
                "is_active": is_active,
            }
            new_card = await self.insert(CardOrm, **new_card_data)

            # Привязываем к системе
            card_system_date = {"card_id": new_card.id, "system_id": self.system.id}
            await self.insert(CardSystemOrm, **card_system_date)

            self.logger.info(f"{card_number} | в БД создана новая карта и привязана к ГПН")

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

    async def gpn_unbind_company_from_cards(self, card_ids: List[str]) -> None:
        await self.init_system()

        stmt = sa_select(CardOrm).where(CardOrm.id.in_(card_ids)).order_by(CardOrm.card_number)
        cards = await self.select_all(stmt)
        card_external_ids = [card.external_id for card in cards]

        # Отвязываем карту от группы в API ГПН
        self.api.unbind_cards_from_group(card_external_ids=card_external_ids)

        # Устанавливаем статус карты в API ГПН
        self.api.block_cards(card_external_ids)

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
            print(f"Организация {j} из {companies_amount}")
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
        limit_sum = max(int(company_available_balance) + spent_sum, 1)
        return limit_sum

    def set_company_limits(self, group_id: str, current_company_limits, limit_sum: int):
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
            if current_limit['productType'] == ProductCategory.FUEL.value["id"]:
                limit_id = current_limit['id']
                if current_limit['sum']['value'] != limit_sum:
                    need_to_update = True
                break

        # if group_id == "1-170U7J6K":
        #     print(f"Идентификатор нового лимита на категорию Топливо: {group_id}")

        if not limit_id or need_to_update:
            if PRODUCTION:
                self.api.set_group_limit(
                    limit_id=limit_id,
                    group_id=group_id,
                    product_category=ProductCategory.FUEL,
                    limit_sum=limit_sum
                )
            else:
                print(f"Псевдо установлен/обновлен лимит на категорию Топливо | LIMIT_ID: {limit_id} | "
                      f"GROUP_ID: {group_id} | LIMIT_SUM: {limit_sum}")

        # Устанавливаем/изменяем лимит на остальные категории
        for not_fuel_category in ProductCategory.not_fuel_categories():
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
                if local_transaction.balance_id:
                    self._irrelevant_balances.add(
                        balance_id=str(local_transaction.balance_id),
                        irrelevancy_date_time=local_transaction.date_time_load
                    )

        # Удаляем помеченные транзакции из БД
        self.logger.info(f'Удалить тразакции из локальной БД: {len(to_delete_local)} шт')
        if len(to_delete_local):
            self.logger.info('Удаляю помеченные локальные транзакции из БД')
            for transaction in to_delete_local:
                await self.delete_object(TransactionOrm, transaction.id)

        # Транзакции от системы, оставшиеся необработанными,
        # записываем в локальную БД.
        self.logger.info(f'Новые тразакции от системы ГПН: {len(remote_transactions)} шт')
        if len(remote_transactions):
            self.logger.info(
                'Начинаю обработку транзакций от системы ГПН, которые не обнаружены в локальной БД'
            )
            await self.process_new_remote_transactions(remote_transactions, transaction_repository)

        # Записываем в БД время последней успешной синхронизации
        await self.update_object(self.system, update_data={"transactions_sync_dt": datetime.now(tz=TZ)})

        # Обновляем время последней транзакции для карт
        await transaction_repository.renew_cards_date_last_use()

    @staticmethod
    def get_equal_remote_transaction(local_transaction: TransactionOrm, remote_transactions: List[Dict[str, Any]]) \
            -> Dict[str, Any] | None:
        for remote_transaction in remote_transactions:
            if remote_transaction['timestamp'] == local_transaction.date_time:
                if remote_transaction['qty'] == abs(local_transaction.fuel_volume):
                    if remote_transaction['sum'] == abs(local_transaction.transaction_sum):
                        return remote_transaction

    async def process_new_remote_transactions(self, remote_transactions: List[Dict[str, Any]],
                                              transaction_repository: TransactionRepository) -> None:
        # Получаем текущие тарифы
        self._bst_list = await transaction_repository.get_balance_system_tariff_list(self.system.id)

        # Получаем историю тарифов
        self._tariffs_history = await transaction_repository.get_tariffs_history(self.system.id)

        # Получаем список продуктов / услуг
        self._outer_goods_list = await transaction_repository.get_outer_goods_list(system_id=self.system.id)

        # Получаем связи карт (Карта-Баланс)
        card_numbers = [transaction['card_number'] for transaction in remote_transactions]
        self._balance_card_relations = await transaction_repository.get_balance_card_relations(
            card_numbers,
            self.system.id
        )

        # Получаем карты
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
                if transaction_data['balance_id']:
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

        purchase = False if remote_transaction['is_storno'] else True
        comments = ''

        # Получаем баланс
        balance_id = self._balance_card_relations.get(card_number, None)
        if not balance_id:
            self.logger.error(f"Не найден баланс для карты {card_number}. Пропускаю обработку транзакции.")
            return None

        # Получаем карту
        card = await get_local_card(card_number, self._local_cards)

        # Получаем товар/услугу
        outer_goods = await self.get_outer_goods(remote_transaction)

        # Получаем тариф
        tariff = get_tariff_on_date_by_balance(
            balance_id=balance_id,
            transaction_date=remote_transaction['timestamp'].date(),
            tariffs_history=self._tariffs_history
        )
        if not tariff:
            tariff = get_current_tariff_by_balance(balance_id=balance_id, bst_list=self._bst_list)

        # Сумма транзакции
        transaction_type = TransactionType.PURCHASE if purchase else TransactionType.REFUND
        transaction_sum = -abs(remote_transaction['sum_no_discount']) if purchase \
            else abs(remote_transaction['sum_no_discount'])

        if remote_transaction['poi_id'] in ["1-11WJG5CA"]:
            # Расчет скидки/наценки для франчайзи
            # Размер скидки
            discount_sum = 0

            # Размер наценки
            fee_percent = 5
            fee_sum = transaction_sum * fee_percent / 100

            comments = "франчайзи: +5%"

        elif remote_transaction['product_id'] in ["00000000000007"]:
            # Расчет скидки/наценки для категории "Бензины"
            # Размер скидки
            discount_sum = 0

            # Размер наценки
            fee_percent = 1
            fee_sum = transaction_sum * fee_percent / 100

            comments = "бензины: +1%"

        else:
            # Размер скидки
            discount_percent = 2
            discount_sum = -transaction_sum * discount_percent / 100

            # Размер наценки
            fee_sum = 0

        # Получаем итоговую сумму
        total_sum = transaction_sum + discount_sum + fee_sum

        transaction_data = dict(
            date_time=remote_transaction['timestamp'],
            date_time_load=datetime.now(tz=TZ),
            transaction_type=transaction_type,
            system_id=self.system.id,
            card_id=card.id,
            balance_id=balance_id,
            azs_code=remote_transaction['poi_id'],
            outer_goods_id=outer_goods.id if outer_goods else None,
            fuel_volume=-remote_transaction['qty'],
            price=remote_transaction['price_no_discount'],
            transaction_sum=transaction_sum,
            tariff_id=tariff.id if tariff else None,
            discount_sum=discount_sum,
            fee_sum=fee_sum,
            total_sum=total_sum,
            company_balance_after=0,
            comments=comments,
        )

        # Это нужно, чтобы в БД у транзакций отличалось время и можно было корректно выбрать транзакцию,
        # которая предшествовала измененной
        time.sleep(0.001)

        return transaction_data

    async def get_outer_goods(self, remote_transaction: Dict[str, Any]) -> OuterGoodsOrm:
        product_id = remote_transaction['product_id']
        # Выполняем поиск товара/услуги
        for goods in self._outer_goods_list:
            if goods.name == product_id:
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
