import time
from datetime import datetime
from typing import Dict, Any, List

from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.celery_tasks.gpn.api import GPNApi
from src.celery_tasks.gpn.config import SYSTEM_SHORT_NAME
from src.celery_tasks.irrelevant_balances import IrrelevantBalances
from src.celery_tasks.transaction_helper import get_local_cards, get_local_card, get_tariff_on_date_by_balance, \
    get_current_tariff_by_balance
from src.config import TZ
from src.database.model.card import CardOrm, BlockingCardReason
from src.database.model.card_type import CardTypeOrm
from src.database.model.models import (CardSystem as CardSystemOrm, Balance as BalanceOrm,
                                       Transaction as TransactionOrm,
                                       OuterGoods as OuterGoodsOrm, BalanceTariffHistory as BalanceTariffHistoryOrm,
                                       BalanceSystemTariff as BalanceSystemTariffOrm)
from src.repositories.base import BaseRepository
from src.repositories.card import CardRepository
from src.repositories.system import SystemRepository
from src.repositories.transaction import TransactionRepository
from src.utils.enums import ContractScheme, TransactionType
from src.utils.log import ColoredLogger


class GPNController(BaseRepository):

    def __init__(self, session: AsyncSession, logger: ColoredLogger):
        super().__init__(session, None)
        self.logger = logger
        self.api = GPNApi(logger)
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
        # await self.load_transactions(need_authorization=False)

        # Возвращаем объект со списком транзакций, начиная с которых требуется пересчитать балансы
        return self._irrelevant_balances

    async def load_balance(self) -> None:
        contract_data = self.api.contract_info()
        balance = float(contract_data['data']['balanceData']['available_amount'])
        self.logger.info('Наш баланс в системе {}: {} руб.'.format(self.system.full_name, balance))

        # Обновляем запись в локальной БД
        await self.update_object(self.system, update_data={
            "balance": balance,
            "balance_sync_dt": datetime.now(tz=TZ)
        })

    async def sync_cards(self) -> None:
        await self.init_system()

        # Получаем список карт от системы
        remote_cards = self.api.get_gpn_cards()
        self.logger.info(f"Количество карт в API ГПН: {len(remote_cards)}")

        # Получаем типы карт
        await self.get_card_types(remote_cards)

        # Получаем список карт из локальной БД, привязанных к ГПН
        local_cards = await get_local_cards(session=self.session, system_id=self.system.id)
        self.logger.info(f"Количество карт в локальной БД (до синхронизации): {len(local_cards)}")

        # Создаем в локальной БД новые карты и привязываем их к ГПН - статус карты из ГПН транслируем на локальную БД.
        # Привязываем в локальной БД карты, открепленные от ГПН - статус не устанавливаем.
        # created_or_updated = False
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
                # created_or_updated = True

        # Локальным картам присваиваем external_id, если не присвоено
        dataset = []
        for local_card in local_cards:
            for remote_card in remote_cards:
                if remote_card['number'] == local_card.card_number:
                    if remote_card['id'] != local_card.external_id:
                        dataset.append({"id": local_card.id, "external_id": remote_card['id']})

        if dataset:
            await self.bulk_update(CardOrm, dataset)

        """
        # Синхронизируем сами группы карт
        await self.sync_card_groups()

        # Получаем список карт из локальной БД, привязанных к ГПН
        if created_or_updated:
            local_cards = await self.get_local_cards()
            self.logger.info(f"Количество карт в локальной БД (после синхронизации): {len(local_cards)}")

        # Из API получаем список групп карт
        gpn_card_groups = self.api.get_card_groups()
        print("Группы карт ГПН:")
        for gpn_group in gpn_card_groups:
            print(gpn_group)
        gpn_group_id_by_name = {gpn_card_group['name']: gpn_card_group['id'] for gpn_card_group in gpn_card_groups}

        # Сравниваем группы карт, присвоенные картам. Записи в локальной БД имеют первичное значение.
        gpn_cards_dict = {card['number']: card for card in remote_cards}
        for local_card in local_cards:
            gpn_card = gpn_cards_dict[local_card.card_number]
            if gpn_card['group_id'] != local_card.group_id:
                if local_card.company_id:
                    self.api.bind_cards_to_group(
                        card_id=gpn_card['id'],
                        group_id=gpn_group_id_by_name[local_card.company.personal_account]
                    )
                else:
                    self.api.unbind_cards_from_group(gpn_card_id=gpn_card['id'])

        # Записываем в БД время последней успешной синхронизации
        await self.update_object(self.system, update_data={"cards_sync_dt": datetime.now(tz=TZ)})
        self.logger.info('Синхронизация карт выполнена')
    """

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

    """
    async def sync_card_groups(self):
        # Из локальной БД получаем список лицевых счетов организаций, которым присвоены карты ГПН.
        # Лицевые счета являются наименованиями для групп карт
        stmt = (
            sa_select(CompanyOrm)
            .select_from(CompanyOrm, CardOrm, CardSystemOrm)
            .where(CompanyOrm.id == CardOrm.company_id)
            .where(CardOrm.id == CardSystemOrm.card_id)
            .where(CardSystemOrm.system_id == self.system.id)
        )
        companies = await self.select_all(stmt)
        # personal_accounts = [company.personal_account for company in companies]

        # Из API получаем список групп карт
        gpn_groups = self.api.get_card_groups()

        # Сравниваем непосредственно группы карт.
        # Совпадающие записи убираем из списков для уменьшения стоимости алгоритмя поиска.
        i = 0
        while i < len(companies):
            company = companies[i].personal_account
            found = False
            for gpn_group in gpn_groups:
                if gpn_group['name'] == company.personal_account:
                    found = True
                    companies[i].remove(company)
                    gpn_groups.remove(gpn_group)
                    break

            if not found:
                i += 1

        # Удаляем в API избыточные группы.
        for group in gpn_groups:
            self.api.delete_gpn_group(group_id=group['id'], group_name=group['name'])

        # Создаем в API недостающие группы.
        for company in companies:
            self.api.create_card_group(group_name=company.personal_account)
    """

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

    async def gpn_bind_company_to_cards(self, card_ids: List[str], personal_account: str, limit_sum: int | float) \
            -> None:
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
            self.logger.info("Пауза 40 сек")
            time.sleep(40)
            self.api.set_card_group_limits([(personal_account, limit_sum)])

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

    async def set_card_group_limit(self, balance_ids: List[str]) -> None:
        if not balance_ids:
            print("Получен пустой список балансов для обновления лимитов на группы карт ГПН")
            return None

        # Получаем параметры баланса и организации
        stmt = (
            sa_select(BalanceOrm)
            .options(
                joinedload(BalanceOrm.company)
            )
            .where(BalanceOrm.id.in_(balance_ids))
        )
        balance = await self.select_first(stmt)

        # Вычисляем доступный лимит
        overdraft_sum = balance.company.overdraft_sum if balance.company.overdraft_on else 0
        boundary_sum = balance.company.min_balance - overdraft_sum
        limit_sum = abs(boundary_sum - balance.balance) if boundary_sum < balance.balance else 1

        # Устанавливаем лимит
        gpn_api = GPNApi(self.logger)
        gpn_api.set_card_group_limits(limits_dataset=[(balance.company.personal_account, limit_sum)])

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
        self._balance_card_relations = await transaction_repository.get_balance_card_relations(card_numbers, self.system.id)

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
        # remote_transaction = {
        #     "id": 9281938435,
        #     "timestamp": "2002-11-28 00:10:00",
        #     "card_id": "15844989",
        #     "poi_id": "1-3GQFQPF",
        #     "terminal_id": "RZ142481",
        #     "type": "P",
        #     "product_id": "00000000000003",
        #     "product_category_id": "НП",
        #     "currency": "RUR",
        #     "check_id": 127523194203,
        #     "stor_transaction_id": 9282453912,
        #     "is_storno": true,
        #     "is_manual_corrention": false,
        #     "qty": -53.10 ,
        #     "price": 54.90,
        #     "price_no_discount": 52.79,
        #     "sum": -2915.19,
        #     "sum_no_discount": -2803.15,
        #     "discount": 112.04,
        #     "exchange_rate": 1,
        #     "card_number": "7005830007328081",
        #     "payment_type": "Карта"
        # }

        # Получаем баланс
        balance_id = self._balance_card_relations.get(card_number, None)
        if not balance_id:
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
        transaction_sum = remote_transaction['sum']

        # Размер скидки
        discount_percent = 0  # 0 / 100
        discount_sum = transaction_sum * discount_percent

        # Размер комиссионного вознаграждения
        fee_percent = float(tariff.fee_percent) / 100 if tariff else 0
        fee_sum = (transaction_sum - discount_sum) * fee_percent

        # Получаем итоговую сумму
        total_sum = transaction_sum - discount_percent + fee_sum

        transaction_data = dict(
            date_time=remote_transaction['timestamp'],
            date_time_load=datetime.now(tz=TZ),
            transaction_type=TransactionType.PURCHASE if remote_transaction['sum'] < 0 else TransactionType.REFUND,
            system_id=self.system.id,
            card_id=card.id,
            balance_id=balance_id,
            azs_code=remote_transaction['poi_id'],
            outer_goods_id=outer_goods.id if outer_goods else None,
            fuel_volume=remote_transaction['qty'],
            price=remote_transaction['price'],
            transaction_sum=transaction_sum,
            tariff_id=tariff.id if tariff else None,
            discount_sum=discount_sum,
            fee_sum=fee_sum,
            total_sum=total_sum,
            company_balance_after=0,
            comments='',
        )

        # Это нужно, чтобы в БД у транзакций отличалось время и можно было корректно выбрать транзакцию,
        # которая предшествовала измененной
        time.sleep(0.001)

        return transaction_data

    async def get_outer_goods(self, remote_transaction: Dict[str, Any]) -> OuterGoodsOrm:
        # Выполняем поиск товара/услуги
        for goods in self._outer_goods_list:
            if goods.external_id == remote_transaction['product_id']:
                return goods

        # Если продукт не найден, то запрашиваем список продуктов у API,
        # добавляем его к имеющемуся списку и выполняем повторный поиск
        gpn_products = self.api.get_products()

        fields = dict(
            name=product_type,
            system_id=self.system.id,
            inner_goods_id=None,
        )
        goods = await self.insert(OuterGoodsOrm, **fields)
        self._outer_goods_list.append(goods)

        return goods
