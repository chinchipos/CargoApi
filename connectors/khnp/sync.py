from sqlalchemy.orm import joinedload
from sqlalchemy import select as sa_select

from configparser import ConfigParser

import os
from datetime import date, timedelta, datetime
from termcolor import colored

from connectors.khnp.parser import KHNPParser
from connectors.sync import get_session
from src.database.models import System, User
from src.repositories.base import BaseRepository
from src.utils.log import ColoredLogger


class KHNPSync(BaseRepository):

    def __init__(self, session: get_session, user: User | None = None):
        super().__init__(session, user)
        self.logger = ColoredLogger(logfile_name='khnp.log', logger_name='KHNP')
        self.parser = KHNPParser(self.logger)

    async def load_cards(self, login=True):
        if login and not self.parser.login():
            return {'success': False, 'message': 'Не удалось авторизоваться на сайте'}

        # Получаем список карт от поставщика услуг
        res = self.parser.get_cards()
        if not res['success']: return res
        self.system_cards = res['cards']

        """
        # Получаем список карт из локальной БД
        res = await self.get_local_cards()
        if not res['success']: return res
        self.local_cards = res['cards']

        # Тип карты по умолчанию
        res = await self.insert_or_update(CardType, 'name', name="Пластиковая карта")
        if not res['success']: return res
        self.default_card_type = res['instance']

        # Сравниваем карты локальные с полученными от поставщика.
        # Создаем в локальной БД карты, которые есть у поставщика услуг, но нет локально
        for system_card in self.system_cards:
            local_card = self.get_equal_local_card(system_card)
            if not local_card:
                # Записываем в БД сведения о новой карте
                res = await self.create_card(system_card['cardNo'])
                if not res['success']: return res

        # Записываем в БД время последней успешной синхронизации
        await self.systems_api.set_cards_sync_dt(self.system, datetime.now())

        return {'success': True}
        """

    """
    def get_equal_local_card(self, system_card):
        i = 0
        length = len(self.local_cards)
        while i < length:
            if self.local_cards[i].card_number == system_card['cardNo']:
                card = self.local_cards[i]
                self.local_cards.pop(i)
                return card
            else:
                i += 1

    async def create_card(self, card_number):
        fields = dict(
            card_number=card_number,
            card_type_id=self.default_card_type.id,
            is_active=True,
            company_id=None,
            belongs_to_car_id=None,
            belongs_to_driver_id=None,
        )
        required_fields = ['card_number', 'card_type_id']
        check = Card.check_required_fields(fields, required_fields)
        if not check['success']: return check
        res = await self.insert(Card, **fields)
        if not res['success']: return res
        card = res['data']
        print(f'Создана карта {card.card_number}')

        return {'success': True, 'card': card}

    async def get_local_cards(self):
        stmt = (
            sa_select(CardSystem)
            .options(
                joinedload(CardSystem.card).joinedload(Card.company)
            )
            .where(CardSystem.system_id == self.system.id)
            .outerjoin(CardSystem.card)
            .order_by(Card.card_number)
        )
        res = await self.select_all(stmt)
        if not res['success']: return res
        cards = [cs.card for cs in res['data']]

        return {'success': True, 'cards': cards}

    async def load_transactions(self, login=True):
        # Получаем список транзакций от поставщика услуг
        res = await self.get_system_transactions(login)
        if not res['success']: return res
        self.system_transactions = res['transactions']
        counter = sum(
            list(map(lambda card_number: len(self.system_transactions.get(card_number)), self.system_transactions)))
        self.logger.info(f'Количество транзакций от поставщика услуг: {counter} шт')
        if not counter:
            return {'success': True, 'calculation_info': {}}

        # Получаем список транзакций из локальной БД
        self.logger.info('Формирую список транзакций из локальной БД.')
        res = await self.get_local_transactions()
        if not res['success']: return res
        self.local_transactions = res['transactions']
        self.logger.info(f'Количество транзакций из локальной БД: {len(self.local_transactions)} шт')

        # Сравниваем транзакции локальные с полученными от поставщика.
        # Идентичные транзакции исключаем из списка, полученного от системы.
        # Удаляем локальные транзакции из БД, которые не были найдены в списке,
        # полученном от системы.
        self.logger.info('Приступаю к процедуре сравнения локальных транзакций с полученными от поставщика.')
        to_delete = []
        self.calculation_info = {}
        for local_transaction in self.local_transactions:
            if local_transaction.card:
                system_transaction = self.get_equal_system_transaction(local_transaction)
                if not system_transaction:
                    # Транзакция присутствует локально, но у поставщика услуг её нет.
                    # Помечаем на удаление локальную транзакцию.
                    to_delete.append(local_transaction)
                    if local_transaction.company_id:
                        if self.calculation_info.get(str(local_transaction.company_id), None):
                            if self.calculation_info[str(local_transaction.company_id)] > local_transaction.date_time:
                                self.calculation_info[str(local_transaction.company_id)] = local_transaction.date_time
                        else:
                            self.calculation_info[str(local_transaction.company_id)] = local_transaction.date_time

        # Удаляем помеченные транзакции из БД
        message = f'Удалить тразакции из локальной БД: {len(to_delete)} шт'
        self.logger.info(colored(message, 'light_red'))
        if len(to_delete):
            self.logger.info('Удаляю помеченные локальные транзакции из БД')
            for transaction in to_delete:
                print('На удаление:', transaction.date_time.isoformat().replace('T', ' '), transaction.card,
                      transaction.company)
            res = await self.delete_by_ids(Transaction, [transaction.id for transaction in to_delete])
            if not res['success']: return res

        # Транзакции от поставщика услуг, оставшиеся необработанными,
        # записываем в локальную БД.
        counter = sum(
            list(map(lambda card_number: len(self.system_transactions.get(card_number)), self.system_transactions)))
        message = f'Новые тразакции от поставщика услуг: {counter} шт'
        self.logger.info(colored(message, 'light_cyan'))
        '''
        for card_number, transactions in self.system_transactions.items():
            print(' ')
            print('Карта:', card_number)
            for transaction in transactions:
                print('   ------------')
                for k, v in transaction.items():
                    print('  ', k, '=', v)
        '''
        if counter:
            self.logger.info('Начинаю обработку транзакции от поставщика услуг, которые не обнаружены в локальной БД')
            res = await self.process_system_transactions()
            if not res['success']: return res

        # Записываем в БД время последней успешной синхронизации
        await self.systems_api.set_transactions_sync_dt(self.system, datetime.now())

        return {'success': True, 'calculation_info': self.calculation_info}

    async def get_system(self):
        stmt = sa_select(System).filter_by(short_name='ХНП')
        res = await self.select_first(stmt)
        return {'success': True, 'system': res['data']} if res['success'] else res

    async def get_system_transactions(self, login=True):
        start_date = date.today() - timedelta(days=self.system.transaction_days)
        end_date = date.today()
        if login and not self.parser.login():
            return {'success': False, 'message': 'Не удалось авторизоваться на сайте'}

        res = self.parser.get_transactions(start_date, end_date)
        if not res['success']: return res
        transactions = res['transactions']
        for card_number, card_transactions in transactions.items():
            for card_transaction in card_transactions:
                card_transaction['date_time'].replace(microsecond=0)

        return {'success': True, 'transactions': transactions}

    async def get_local_transactions(self):
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
        res = await self.select_all(stmt)
        if not res['success']: return res
        transactions = res['data']
        for tr in transactions:
            tr.date_time.replace(microsecond=0)

        return {'success': True, 'transactions': transactions}

    def get_equal_system_transaction(self, local_transaction):
        card_transactions = self.system_transactions.get(local_transaction.card.card_number, [])
        for system_transaction in card_transactions:
            if system_transaction['date_time'] == local_transaction.date_time:
                if system_transaction['fuel_volume'] == abs(local_transaction.fuel_volume):
                    if system_transaction['money_request'] == abs(local_transaction.transaction_sum):
                        transaction = system_transaction
                        card_transactions.remove(system_transaction)

                        # Если список транзакций по карте пуст,
                        # то удаляем из словаря запись о карте.
                        if not card_transactions:
                            self.system_transactions.pop(local_transaction.card.card_number)

                        return transaction

    async def process_system_transactions(self):
        # Получаем из локальной БД список оставшихся карт.
        # Предполагаем, что перед прогрузкой транзакций была выполнена прогрузка карт.
        card_numbers = [card_number for card_number in self.system_transactions]
        stmt = (
            sa_select(Card)
            .options(
                joinedload(Card.company).joinedload(Company.tariff)
            )
            .where(Card.card_number.in_(card_numbers))
        )
        res = await self.select_all(stmt)
        if not res['success']: return res
        self.cards = res['data']

        # Получаем список товаров/услуг этого поставщика
        stmt = sa_select(OuterGoods).where(OuterGoods.system_id == self.system.id)
        res = await self.select_all(stmt)
        if not res['success']: return res
        self.outer_goods = res['data']

        # Инициализируем API модуль для работы с тарифами
        self.tariffs_api = TariffsApi(self.asession)

        # Подготавливаем список транзакций для сохранения в БД
        transactions_to_save = []
        for card_number, card_transactions in self.system_transactions.items():
            for card_transaction in card_transactions:
                res = await self.process_system_transaction(card_number, card_transaction)
                if not res['success']: return res
                if res['transaction']:
                    transaction = res['transaction']
                    transactions_to_save.append(transaction)
                    if transaction['company_id']:
                        if self.calculation_info.get(str(transaction['company_id']), None):
                            if self.calculation_info[str(transaction['company_id'])] > transaction['date_time']:
                                self.calculation_info[str(transaction['company_id'])] = transaction['date_time']
                        else:
                            self.calculation_info[str(transaction['company_id'])] = transaction['date_time']

        # Сохраняем транзакции в БД
        res = await self.bulk_insert_or_update(transactions_to_save, Transaction)
        if not res['success']: return res

        return {'success': True}

    async def process_system_transaction(self, card_number, system_transaction):
        # system_transaction = {
        #    azs: АЗС № 01 (АБНС)           <class 'str'>
        #    product_type: Любой            <class 'str'>
        #    price: 0.0                     <class 'float'>
        #    liters_ordered: 0.0            <class 'float'>
        #    liters_received: 0.0           <class 'float'>
        #    money_request: 47318.4         <class 'float'>
        #    money_rest: 167772.15          <class 'float'>
        #    type: Кредит                   <class 'str'>
        #    date: 16.03.2024               <class 'str'>
        #    time: 11:24:47                 <class 'str'>
        #    date_time: 2024-03-16 11:24:47 <class 'datetime.datetime'>
        # }

        # Выполняем проверки, т.к. не все транзакции от поставщика услуг нужно принять
        allowed_transaction_types = [
            "Дебет",
            "Кредит, возврат на карту",
            "Возмещение"
        ]
        if not system_transaction['azs']: return {'success': True, 'transaction': None}
        # if system_transaction['product_type'] == 'Любой': return {'success': True, 'transaction': None}
        if not system_transaction['price']: return {'success': True, 'transaction': None}
        if system_transaction['type'] not in allowed_transaction_types: return {'success': True, 'transaction': None}
        if not system_transaction['date']: return {'success': True, 'transaction': None}
        if not system_transaction['time']: return {'success': True, 'transaction': None}

        # Получаем тип транзакции
        debit = True if system_transaction['type'] == "Дебет" else False

        # Получаем карту
        res = self.get_card(card_number)
        if not res['success']: return res
        card = res['card']

        # Получаем товар/услугу
        res = await self.get_outer_goods(system_transaction)
        if not res['success']: return res
        goods = res['outer_goods']

        # Получаем тариф
        res = await self.tariffs_api.get_tariff_by_date(card.company, system_transaction['date_time'].date())
        if not res['success']: return res
        tariff = res['tariff']

        # Объем топлива
        fuel_volume = system_transaction['liters_ordered'] if debit else -system_transaction['liters_ordered']

        # Сумма транзакции
        transaction_sum = -system_transaction['money_request'] if debit else system_transaction['money_request']

        # Размер скидки
        discount_percent = 0  # 0 / 100
        discount_sum = transaction_sum * discount_percent

        # Размер комиссионного вознаграждения
        fee_percent = float(tariff.fee_percent) / 100 if tariff else 0
        fee_sum = (transaction_sum - discount_sum) * fee_percent

        # Получаем итоговую сумму
        total_sum = transaction_sum - discount_percent + fee_sum

        transaction = dict(
            date_time=system_transaction['date_time'],
            debit=debit,
            system_id=self.system.id,
            card_id=card.id,
            company_id=card.company_id,
            azs_code=system_transaction['azs'],
            outer_goods_id=goods.id if goods else None,
            fuel_volume=fuel_volume,
            price=system_transaction['price'],
            transaction_sum=transaction_sum,
            tariff_id=tariff.id if tariff else None,
            discount_sum=discount_sum,
            fee_sum=fee_sum,
            total_sum=total_sum,
            company_balance_after=0,
            comments='',
        )

        return {'success': True, 'transaction': transaction}

    def get_card(self, card_number):
        for card in self.cards:
            if card.card_number == card_number:
                return {'success': True, 'card': card}

        return {'success': False, 'message': f'Карта с номером {card_number} не найдена в БД'}

    async def get_outer_goods(self, system_transaction):
        # Выполняем поиск товара/услуги
        product_type = system_transaction['product_type'].strip()
        for goods in self.outer_goods:
            if goods.name == product_type:
                return {'success': True, 'outer_goods': goods}

        # Если товар/услуга не найден(а), то создаем его(её)
        fields = dict(
            name=product_type,
            system_id=self.system.id,
            inner_goods_id=None,
        )
        required_fields = ['name']
        check = OuterGoods.check_required_fields(fields, required_fields)
        if not check['success']: return check
        res = await self.insert(OuterGoods, **fields)
        if not res['success']: return res
        goods = res['instance']
        self.outer_goods.append(goods)

        return {'success': True, 'outer_goods': goods}

    async def load_balance(self, login=True):
        if login and not self.parser.login():
            return {'success': False, 'message': 'Не удалось авторизоваться на сайте'}

        # Получаем наш баланс у поставщика услуг
        res = self.parser.get_balance()
        if not res['success']: return res
        balance = float(res['balance'])

        # Обновляем баланс в БД
        res = await self.systems_api.set_balance(self.system, balance)
        if not res['success']: return res

        return {'success': True}
    """
