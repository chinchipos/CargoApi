from datetime import datetime, date, timedelta
from typing import Dict, Any, List

from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.connectors.exceptions import sync_logger
from src.connectors.khnp.config import SYSTEM_SHORT_NAME
from src.connectors.khnp.exceptions import KHNPConnectorError
from src.connectors.khnp.parser import KHNPParser
from src.database.models import User, CardSystem, Card, System, CardType, Transaction, OuterGoods, Company
from src.repositories.base import BaseRepository
from src.repositories.system import SystemRepository
from src.repositories.tariff import TariffRepository


class KHNPConnector(BaseRepository):

    def __init__(self, session: AsyncSession, user: User | None = None):
        super().__init__(session, user)
        self.parser = KHNPParser()
        self.system = None
        self.system_repository = None
        self.local_cards = None
        self.provider_cards = None
        self.outer_goods = None
        self.tariff_repository = None

    def get_system_repository(self):
        if not self.system_repository:
            self.system_repository = SystemRepository(self.session, self.user)

        return self.system_repository

    async def get_system(self) -> System:
        if not self.system:
            system_repository = self.get_system_repository()
            self.system = await system_repository.get_system_by_short_name(SYSTEM_SHORT_NAME)

        return self.system

    async def load_balance(self, need_authorization: bool = True) -> None:
        if need_authorization:
            self.parser.login()

        # Получаем систему
        system = await self.get_system()

        # Получаем наш баланс у поставщика услуг
        balance = self.parser.get_balance()
        sync_logger.info('Наш баланс в системе {}: {} руб.'.format(system.full_name, balance))

        # Обновляем запись в локальной БД
        await self.update_object(system, update_data={"balance": balance})
        sync_logger.info('Обновлен баланс в локальной БД')

    async def get_local_cards(self) -> List[CardSystem]:
        # Получаем систему
        system = await self.get_system()

        stmt = (
            sa_select(CardSystem)
            .options(
                joinedload(CardSystem.card).joinedload(Card.company).joinedload(Company.tariff)
            )
            .where(CardSystem.system_id == system.id)
            .outerjoin(CardSystem.card)
            .order_by(Card.card_number)
        )
        self.local_cards = await self.select_all(stmt)

        return self.local_cards

    def get_equal_local_card(self, provider_card: Dict[str, Any], local_cards: List[CardSystem]) -> Card:
        i = 0
        length = len(local_cards)
        while i < length:
            if local_cards[i].card.card_number == provider_card['cardNo']:
                card = local_cards.pop(i).card
                return card
            else:
                i += 1

    async def create_card(self, card_number: str, default_card_type_id: str) -> Card:
        fields = dict(
            card_number=card_number,
            card_type_id=default_card_type_id,
            is_active=True,
            company_id=None,
            belongs_to_car_id=None,
            belongs_to_driver_id=None,
        )
        new_card = await self.insert(Card, **fields)
        sync_logger.info(f'Создана карта {new_card.card_number}')
        return new_card

    def get_provider_cards(self) -> List[Dict[str, Any]]:
        if not self.provider_cards:
            self.provider_cards = self.parser.get_cards()

        return self.provider_cards

    async def load_cards(self, need_authorization: bool = True) -> None:
        if need_authorization:
            self.parser.login()

        # Получаем список карт от поставщика услуг
        provider_cards = self.get_provider_cards()
        
        # Получаем список карт из локальной БД
        local_cards = await self.get_local_cards()

        # Тип карты по умолчанию
        stmt = sa_select(CardType).where(CardType.name == 'Пластиковая карта')
        default_card_type = await self.select_first(stmt)

        # Сравниваем карты локальные с полученными от поставщика.
        # Создаем в локальной БД карты, которые есть у поставщика услуг, но нет локально

        for provider_card in provider_cards:
            local_card = self.get_equal_local_card(provider_card, local_cards)
            if not local_card:
                # Записываем в БД сведения о новой карте
                await self.create_card(provider_card['cardNo'], default_card_type.id)

        # Записываем в БД время последней успешной синхронизации
        system = await self.get_system()
        await self.update_object(system, update_data={"cards_sync_dt": datetime.now()})
        sync_logger.info('Синхронизация карт выполнена')

    async def get_provider_transactions(self, need_authorization: bool = True) -> Dict[str, Any]:
        if need_authorization:
            self.parser.login()

        # Получаем систему
        system = await self.get_system()

        # Устанавливаем период для транзакций
        start_date = date.today() - timedelta(days=system.transaction_days)
        end_date = date.today()

        # Получаем транзакции
        transactions = self.parser.get_transactions(start_date, end_date)
        return transactions

    async def get_local_transactions(self) -> List[Transaction]:
        start_date = date.today() - timedelta(days=self.system.transaction_days)
        stmt = (
            sa_select(Transaction)
            .options(
                joinedload(Transaction.card),
                joinedload(Transaction.company),
                joinedload(Transaction.outer_goods),
                joinedload(Transaction.tariff)
            )
            .where(Transaction.date_time >= start_date)
            .where(Transaction.system_id == self.system.id)
            .outerjoin(Transaction.card)
            .order_by(Card.card_number, Transaction.date_time)
        )
        transactions = await self.select_all(stmt)
        for tr in transactions:
            tr.date_time.replace(microsecond=0)

        return transactions

    def get_equal_provider_transaction(
        self,
        local_transaction: Transaction,
        provider_transactions: Dict[str, Any]
    ) -> Dict[str, Any]:
        card_transactions = provider_transactions.get(local_transaction.card.card_number, [])
        for provider_transaction in card_transactions:
            if provider_transaction['date_time'] == local_transaction.date_time:
                if provider_transaction['fuel_volume'] == abs(local_transaction.fuel_volume):
                    if provider_transaction['money_request'] == abs(local_transaction.transaction_sum):
                        transaction = provider_transaction
                        card_transactions.remove(provider_transaction)

                        # Если список транзакций по карте пуст,
                        # то удаляем из словаря запись о карте.
                        if not card_transactions:
                            provider_transactions.pop(local_transaction.card.card_number)

                        return transaction

    async def get_local_card(self, card_number) -> Card:
        local_cards = await self.get_local_cards()
        for card_system in local_cards:
            if card_system.card.card_number == card_number:
                return card_system.card

        raise KHNPConnectorError(trace=True, message=f'Карта с номером {card_number} не найдена в БД')

    async def get_all_outer_goods(self) -> List[OuterGoods]:
        if not self.outer_goods:
            system = await self.get_system()
            stmt = sa_select(OuterGoods).where(OuterGoods.system_id == system.id)
            self.outer_goods = await self.select_all(stmt)

        return self.outer_goods

    async def get_single_outer_goods(self, provider_transaction: Dict[str, Any]) -> OuterGoods:
        all_outer_goods = await self.get_all_outer_goods()

        # Выполняем поиск товара/услуги
        product_type = provider_transaction['product_type']
        for goods in all_outer_goods:
            if goods.name == product_type:
                return goods

        # Если товар/услуга не найден(а), то создаем его(её)
        fields = dict(
            name=product_type,
            system_id=self.system.id,
            inner_goods_id=None,
        )
        goods = await self.insert(OuterGoods, **fields)
        self.outer_goods.append(goods)

        return goods

    async def get_tariff_repository(self):
        if not self.tariff_repository:
            self.tariff_repository = TariffRepository(self.session, self.user)

        return self.tariff_repository

    async def process_provider_transaction(self, card_number, provider_transaction: Dict[str, Any]) -> Dict[str, Any]:
        # system_transaction = {
        #    azs: АЗС № 01 (АБНС)           <class 'str'>
        #    product_type: Любой            <class 'str'>
        #    price: 0.0                     <class 'float'>
        #    liters_ordered: 0.0            <class 'float'>
        #    liters_received: 0.0           <class 'float'>
        #    money_request: 47318.4         <class 'float'>
        #    money_rest: 167772.15          <class 'float'>
        #    type_: Кредит                   <class 'str'>
        #    date: 16.03.2024               <class 'str'>
        #    time: 11:24:47                 <class 'str'>
        #    date_time: 2024-03-16 11:24:47 <class 'datetime.datetime'>
        # }

        # Получаем тип транзакции
        debit = True if provider_transaction['type'] == "Дебет" else False

        # Получаем карту
        card = await self.get_local_card(card_number)

        # Получаем систему
        system = await self.get_system()

        # Получаем товар/услугу
        single_outer_goods = await self.get_single_outer_goods(provider_transaction)

        # Получаем тариф
        tariff_repository = await self.get_tariff_repository()
        tariff = await tariff_repository.get_company_tariff_on_date(
            company=card.company,
            _date_=provider_transaction['date_time'].date()
        ) if card.company else None

        # Объем топлива
        fuel_volume = provider_transaction['liters_ordered'] if debit else -provider_transaction['liters_ordered']

        # Сумма транзакции
        transaction_sum = -provider_transaction['money_request'] if debit else provider_transaction['money_request']

        # Размер скидки
        discount_percent = 0  # 0 / 100
        discount_sum = transaction_sum * discount_percent

        # Размер комиссионного вознаграждения
        fee_percent = float(tariff.fee_percent) / 100 if tariff else 0
        fee_sum = (transaction_sum - discount_sum) * fee_percent

        # Получаем итоговую сумму
        total_sum = transaction_sum - discount_percent + fee_sum

        transaction_data = dict(
            date_time=provider_transaction['date_time'],
            is_debit=debit,
            system_id=system.id,
            card_id=card.id,
            company_id=card.company_id,
            azs_code=provider_transaction['azs'],
            outer_goods_id=single_outer_goods.id if single_outer_goods else None,
            fuel_volume=fuel_volume,
            price=provider_transaction['price'],
            transaction_sum=transaction_sum,
            tariff_id=tariff.id if tariff else None,
            discount_sum=discount_sum,
            fee_sum=fee_sum,
            total_sum=total_sum,
            company_balance_after=0,
            comments='',
        )

        return transaction_data

    def update_calculation_info(
        self,
        company_id: str,
        transaction_date_time: datetime,
        calculation_info: Dict[str, Any]
    ) -> None:
        if calculation_info.get(company_id, None):
            if calculation_info[company_id] > transaction_date_time:
                calculation_info[company_id] = transaction_date_time
        else:
            calculation_info[company_id] = transaction_date_time

    async def process_provider_transactions(
        self,
        provider_transactions: Dict[str, Any],
        calculation_info: Dict[str, Any]
    ) -> None:
        # Подготавливаем список транзакций для сохранения в БД
        transactions_to_save = []
        for card_number, card_transactions in provider_transactions.items():
            for card_transaction in card_transactions:
                transaction_data = await self.process_provider_transaction(card_number, card_transaction)
                if transaction_data:
                    transactions_to_save.append(transaction_data)
                    if transaction_data['company_id']:
                        self.update_calculation_info(
                            company_id=str(transaction_data['company_id']),
                            transaction_date_time=transaction_data['date_time'],
                            calculation_info=calculation_info
                        )

        # Сохраняем транзакции в БД
        await self.bulk_insert_or_update(Transaction, transactions_to_save)

    async def load_transactions(self, need_authorization: bool = True) -> Dict[str, Any]:
        # Получаем список транзакций от поставщика услуг
        provider_transactions = await self.get_provider_transactions(need_authorization)
        counter = sum(list(map(
            lambda card_number: len(provider_transactions.get(card_number)), provider_transactions
        )))
        sync_logger.info(f'Количество транзакций от поставщика услуг: {counter} шт')
        if not counter:
            return {}

        # Получаем список транзакций из локальной БД
        sync_logger.info('Формирую список транзакций из локальной БД')
        local_transactions = await self.get_local_transactions()
        sync_logger.info(f'Количество транзакций из локальной БД: {len(local_transactions)} шт')

        # Сравниваем транзакции локальные с полученными от поставщика.
        # Идентичные транзакции исключаем из списка, полученного от системы.
        # Удаляем локальные транзакции из БД, которые не были найдены в списке,
        # полученном от системы.
        sync_logger.info('Приступаю к процедуре сравнения локальных транзакций с полученными от поставщика')
        to_delete = []
        calculation_info = {}
        for local_transaction in local_transactions:
            if local_transaction.card:
                system_transaction = self.get_equal_provider_transaction(local_transaction, provider_transactions)
                if not system_transaction:
                    # Транзакция присутствует локально, но у поставщика услуг её нет.
                    # Помечаем на удаление локальную транзакцию.
                    to_delete.append(local_transaction)
                    if local_transaction.company_id:
                        self.update_calculation_info(
                            company_id=local_transaction.company_id,
                            transaction_date_time=local_transaction.date_time,
                            calculation_info=calculation_info
                        )

        # Удаляем помеченные транзакции из БД
        sync_logger.info(f'Удалить тразакции из локальной БД: {len(to_delete)} шт')
        if len(to_delete):
            sync_logger.info('Удаляю помеченные локальные транзакции из БД')
            for transaction in to_delete:
                print('На удаление:', transaction.date_time.isoformat().replace('T', ' '), transaction.card,
                      transaction.company)

            for transaction in to_delete:
                await self.delete_object(Transaction, transaction.id)

        # Транзакции от поставщика услуг, оставшиеся необработанными,
        # записываем в локальную БД.
        counter = sum(list(map(
            lambda card_number: len(provider_transactions.get(card_number)), provider_transactions
        )))
        sync_logger.info(f'Новые тразакции от поставщика услуг: {counter} шт')

        if counter:
            sync_logger.info('Начинаю обработку транзакции от поставщика услуг, которые не обнаружены в локальной БД')
            await self.process_provider_transactions(provider_transactions, calculation_info)

        # Записываем в БД время последней успешной синхронизации
        system = await self.get_system()
        await self.update_object(system, update_data={"transactions_sync_dt": datetime.now()})

        return calculation_info
