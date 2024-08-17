from datetime import datetime, date, timedelta
from time import sleep
from typing import Dict, Any, List, Tuple

from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from src.celery_app.irrelevant_balances import IrrelevantBalances
from src.celery_app.khnp.api import KHNPParser, CardStatus
from src.celery_app.khnp.config import SYSTEM_SHORT_NAME
from src.celery_app.transaction_helper import get_local_cards, get_local_card, get_tariff_on_date_by_balance, \
    get_current_tariff_by_balance
from src.config import TZ
from src.database.model.card import CardOrm, BlockingCardReason
from src.database.model.card_type import CardTypeOrm
from src.database.model.models import (Transaction as TransactionOrm,
                                       BalanceTariffHistory as BalanceTariffHistoryOrm,
                                       CardSystem as CardSystemOrm, BalanceSystemTariff as BalanceSystemTariffOrm)
from src.database.model.goods import OuterGoodsOrm
from src.repositories.base import BaseRepository
from src.repositories.card import CardRepository
from src.repositories.system import SystemRepository
from src.repositories.transaction import TransactionRepository
from src.utils.enums import ContractScheme, TransactionType
from src.utils.loggers import get_logger


class KHNPController(BaseRepository):

    def __init__(self, session: AsyncSession):
        super().__init__(session, None)
        self.logger = get_logger(name="KHNPController", filename="celery.log")
        self.parser = KHNPParser()
        self.system = None
        self.local_cards: List[CardOrm] = []
        self.khnp_cards: List[Dict[str, Any]] = []
        # self.outer_goods: List[OuterGoodsOrm] = []
        self._tariffs_history: List[BalanceTariffHistoryOrm] = []
        self._bst_list: List[BalanceSystemTariffOrm] = []
        self._balance_card_relations: Dict[str, str] = {}
        self._local_cards: List[CardOrm] = []
        self._irrelevant_balances = IrrelevantBalances()
        self._outer_goods_list: List[OuterGoodsOrm] = []

    async def sync(self) -> IrrelevantBalances:
        await self.init_system()

        # Прогружаем наш баланс
        await self.load_balance(need_authorization=True)

        # Синхронизируем карты по номеру
        await self.sync_cards_by_number(need_authorization=False)

        # Прогружаем транзакции
        await self.load_transactions(need_authorization=False)

        # Возвращаем объект со списком транзакций, начиная с которых требуется пересчитать балансы
        return self._irrelevant_balances

    async def init_system(self) -> None:
        system_repository = SystemRepository(self.session)
        self.system = await system_repository.get_system_by_short_name(
            system_fhort_name=SYSTEM_SHORT_NAME,
            scheme=ContractScheme.OVERBOUGHT
        )

    async def load_balance(self, need_authorization: bool = True) -> None:
        if need_authorization:
            self.parser.login()

        # Получаем наш баланс у поставщика услуг
        balance = self.parser.get_balance()
        self.logger.info('Наш баланс в системе {}: {} руб.'.format(self.system.full_name, balance))

        # Обновляем запись в локальной БД
        await self.update_object(self.system, update_data={
            "balance": balance,
            "balance_sync_dt": datetime.now(tz=TZ)
        })

    """
    async def get_local_cards(self, card_numbers: List[str] | None = None) -> List[CardOrm]:
        card_repository = CardRepository(self.session)
        # self.local_cards = await card_repository.get_cards_by_numbers(card_numbers, self.system.id)
        self.local_cards = await card_repository.get_cards_by_filters(
            system_id=self.system.id,
            card_numbers=card_numbers
        )
        return self.local_cards
    """

    @staticmethod
    def get_equal_local_card(provider_card: Dict[str, Any], local_cards: List[CardOrm]) -> CardOrm:
        i = 0
        length = len(local_cards)
        while i < length:
            if local_cards[i].card_number == provider_card['cardNo']:
                card = local_cards.pop(i)
                return card
            else:
                i += 1

    def get_khnp_cards(self) -> List[Dict[str, Any]]:
        if not self.khnp_cards:
            self.khnp_cards = self.parser.get_cards()

        return self.khnp_cards

    async def sync_cards_by_number(self, need_authorization: bool = True) -> None:
        if need_authorization:
            self.parser.login()

        # Получаем список карт от поставщика услуг
        khnp_cards = self.get_khnp_cards()

        # Получаем список карт из локальной БД
        local_cards = await get_local_cards(
            session=self.session,
            system_id=self.system.id
        )

        # Сравниваем карты локальные с полученными от поставщика.
        await self.compare_cards(khnp_cards, local_cards)

        # Записываем в БД время последней успешной синхронизации
        await self.update_object(self.system, update_data={"cards_sync_dt": datetime.now(tz=TZ)})
        self.logger.info('Синхронизация карт выполнена')

    async def get_provider_transactions(self, need_authorization: bool = True) -> Dict[str, Any]:
        if need_authorization:
            self.parser.login()

        # Устанавливаем период для транзакций
        start_date = date.today() - timedelta(days=self.system.transaction_days)
        end_date = date.today()

        # Получаем транзакции
        transactions = self.parser.get_transactions(start_date, end_date)
        return transactions

    """
    async def get_local_transactions(self) -> List[TransactionOrm]:
        start_date = date.today() - timedelta(days=self.system.transaction_days)
        stmt = (
            sa_select(TransactionOrm)
            .options(
                joinedload(TransactionOrm.card),
                joinedload(TransactionOrm.company),
                joinedload(TransactionOrm.outer_goods),
                joinedload(TransactionOrm.tariff)
            )
            .where(TransactionOrm.date_time >= start_date)
            .where(TransactionOrm.system_id == self.system.id)
            .outerjoin(TransactionOrm.card)
            .order_by(CardOrm.card_number, TransactionOrm.date_time)
        )
        transactions = await self.select_all(stmt)
        for tr in transactions:
            tr.date_time.replace(microsecond=0)

        return transactions
    """

    @staticmethod
    def get_equal_remote_transaction(local_transaction: TransactionOrm,
                                     provider_transactions: Dict[str, Any]) -> Dict[str, Any]:

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

    """
    async def get_local_card(self, card_number) -> CardOrm:
        for card in self._local_cards:
            if card.card_number == card_number:
                return card

        raise CeleryError(trace=True, message=f'Карта с номером {card_number} не найдена в БД')
    """
    """
    async def get_all_outer_goods(self) -> List[OuterGoodsOrm]:
        if not self.outer_goods:
            stmt = sa_select(OuterGoodsOrm).where(OuterGoodsOrm.system_id == self.system.id)
            self.outer_goods = await self.select_all(stmt)

        return self.outer_goods
    """
    async def get_single_outer_goods(self, provider_transaction: Dict[str, Any]) -> OuterGoodsOrm:
        # all_outer_goods = await self.get_all_outer_goods()
        # Выполняем поиск товара/услуги
        product_type = provider_transaction['product_type']
        for goods in self._outer_goods_list:
            if goods.name == product_type:
                return goods

        # Если товар/услуга не найден(а), то создаем его(её)
        fields = dict(
            name=product_type,
            system_id=self.system.id,
            inner_goods_id=None,
        )
        goods = await self.insert(OuterGoodsOrm, **fields)
        self._outer_goods_list.append(goods)

        return goods

    """
    async def _get_tariffs_history(self) -> List[BalanceTariffHistoryOrm]:
        bth = aliased(BalanceTariffHistoryOrm, name="bth")
        stmt = (
            sa_select(bth)
            .options(
                joinedload(bth.tariff)
                .load_only(TariffOrm.id, TariffOrm.fee_percent)
            )
            .where(bth.system_id == self.system.id)
        )
        tariffs_history = await self.select_all(stmt)
        return tariffs_history
    """
    """
    def _get_tariff_on_date_by_balance(self, balance_id: str, transaction_date: date) -> TariffOrm:
        for th in self._tariffs_history:
            if th.balance_id == balance_id and th.start_date <= transaction_date \
                    and (th.end_date is None or th.end_date > transaction_date):
                return th.tariff
    """
    """
    async def _get_balance_system_tariff_list(self) -> List[BalanceSystemTariffOrm]:
        bst = aliased(BalanceSystemTariffOrm, name="bst")
        stmt = (
            sa_select(bst)
            .options(
                joinedload(bst.tariff)
                .load_only(TariffOrm.id, TariffOrm.fee_percent)
            )
            .where(bst.system_id == self.system.id)
        )
        balance_system_tariff_list = await self.select_all(stmt)
        return balance_system_tariff_list
    """
    """
    def _get_current_tariff_by_balance(self, balance_id: str) -> TariffOrm:
        for bst in self._bst_list:
            if bst.balance_id == balance_id:
                return bst.tariff
    """

    async def process_new_remote_transaction(self, card_number: str,
                                             remote_transaction: Dict[str, Any]) -> Dict[str, Any] | None:
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
        debit = True if remote_transaction['type'] == "Дебет" else False

        # Получаем карту
        card = await get_local_card(card_number, self._local_cards)
        # card = await self.get_local_card(card_number)

        # Получаем баланс
        balance_id = self._balance_card_relations.get(card_number, None)
        if not balance_id:
            self.logger.error(f"Не найден баланс для карты {card_number}. Пропускаю обработку транзакции.")
            return None

        # Получаем товар/услугу
        single_outer_goods = await self.get_single_outer_goods(remote_transaction)

        # Получаем тариф
        tariff = get_tariff_on_date_by_balance(
            balance_id=balance_id,
            transaction_date=remote_transaction['date_time'].date(),
            tariffs_history=self._tariffs_history
        )
        if not tariff:
            tariff = get_current_tariff_by_balance(balance_id=balance_id, bst_list=self._bst_list)
            # tariff = self._get_current_tariff_by_balance(balance_id)

        # Объем топлива
        fuel_volume = -remote_transaction['liters_ordered'] if debit else remote_transaction['liters_received']

        # Сумма транзакции
        transaction_sum = -remote_transaction['money_request'] if debit else remote_transaction['money_request']

        # Размер скидки
        discount_percent = 0  # 0 / 100
        discount_sum = transaction_sum * discount_percent

        # Размер комиссионного вознаграждения
        fee_percent = float(tariff.fee_percent) / 100 if tariff else 0
        fee_sum = (transaction_sum - discount_sum) * fee_percent

        # Получаем итоговую сумму
        total_sum = transaction_sum - discount_sum + fee_sum

        transaction_data = dict(
            date_time=remote_transaction['date_time'],
            date_time_load=datetime.now(tz=TZ),
            transaction_type=TransactionType.PURCHASE if debit else TransactionType.REFUND,
            system_id=self.system.id,
            card_id=card.id,
            balance_id=balance_id,
            azs_code=remote_transaction['azs'],
            outer_goods_id=single_outer_goods.id if single_outer_goods else None,
            fuel_volume=fuel_volume,
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
        sleep(0.001)

        return transaction_data

    async def process_new_remote_transactions(self, remote_transactions: Dict[str, Any],
                                              transaction_repository: TransactionRepository) -> None:
        # Получаем текущие тарифы
        self._bst_list = await transaction_repository.get_balance_system_tariff_list(self.system.id)

        # Получаем историю тарифов
        self._tariffs_history = await transaction_repository.get_tariffs_history(self.system.id)

        # Получаем список продуктов / услуг
        self._outer_goods_list = await transaction_repository.get_outer_goods_list(system_id=self.system.id)

        # Получаем связи карт (Карта-Баланс)
        card_numbers = [card_number for card_number in remote_transactions.keys()]
        self._balance_card_relations = await transaction_repository.get_balance_card_relations(
            card_numbers, self.system.id)
        # await self._set_balance_card_relations(card_numbers)

        # Получаем карты
        self._local_cards = await get_local_cards(
            session=self.session,
            system_id=self.system.id,
            card_numbers=card_numbers
        )

        # Подготавливаем список транзакций для сохранения в БД
        transactions_to_save = []
        for card_number, card_transactions in remote_transactions.items():
            for card_transaction in card_transactions:
                transaction_data = await self.process_new_remote_transaction(card_number, card_transaction)
                if transaction_data:
                    transactions_to_save.append(transaction_data)
                    if transaction_data['balance_id']:
                        self._irrelevant_balances.add(
                            balance_id=str(transaction_data['balance_id']),
                            irrelevancy_date_time=transaction_data['date_time_load']
                        )

        # Сохраняем транзакции в БД
        await self.bulk_insert_or_update(TransactionOrm, transactions_to_save)

    """
    async def _set_balance_card_relations(self, card_numbers: List[str]) -> None:
        stmt = (
            sa_select(CardOrm.card_number, BalanceOrm.id)
            .select_from(BalanceSystemTariffOrm, BalanceOrm, CompanyOrm, CardOrm, CardSystemOrm)
            .where(CardOrm.card_number.in_(card_numbers))
            .where(CardSystemOrm.card_id == CardOrm.id)
            .where(CardSystemOrm.system_id == self.system.id)
            .where(BalanceSystemTariffOrm.system_id == self.system.id)
            .where(BalanceOrm.id == BalanceSystemTariffOrm.balance_id)
            .where(CompanyOrm.id == BalanceOrm.company_id)
            .where(CardOrm.company_id == CompanyOrm.id)
        )
        dataset = await self.select_all(stmt, scalars=False)
        self._balance_card_relations = {data[0]: data[1] for data in dataset}
    """

    """
    async def renew_cards_date_last_use(self) -> None:
        date_last_use_subquery = (
            sa_select(func.max(TransactionOrm.date_time))
            .where(TransactionOrm.card_id == CardOrm.id)
            .scalar_subquery()
        )
        stmt = sa_update(CardOrm).values(date_last_use=date_last_use_subquery)
        await self.session.execute(stmt)
        await self.session.commit()
    """

    async def load_transactions(self, need_authorization: bool = True):
        # Получаем список транзакций от поставщика услуг
        remote_transactions = await self.get_provider_transactions(need_authorization)
        counter = sum(list(map(
            lambda card_number: len(remote_transactions.get(card_number)), remote_transactions
        )))
        self.logger.info(f'Количество транзакций от системы ХНП: {counter} шт')
        if not counter:
            return None

        # Получаем список транзакций из локальной БД
        transaction_repository = TransactionRepository(self.session, None)
        local_transactions = await transaction_repository.get_recent_system_transactions(
            system_id=self.system.id,
            transaction_days=self.system.transaction_days
        )
        # local_transactions = await self.get_local_transactions()
        self.logger.info(f'Количество транзакций из локальной БД: {len(local_transactions)} шт')

        # Сравниваем транзакции локальные с полученными от системы.
        # Идентичные транзакции исключаем из списка, полученного от системы.
        # Удаляем локальные транзакции из БД, которые не были найдены в списке,
        # полученном от системы.
        self.logger.info('Приступаю к процедуре сравнения локальных транзакций с полученными от системы ХНП')
        to_delete = []
        for local_transaction in local_transactions:
            if local_transaction.card:
                remote_transaction = self.get_equal_remote_transaction(local_transaction, remote_transactions)
                if not remote_transaction:
                    # Транзакция присутствует локально, но у поставщика услуг её нет.
                    # Помечаем на удаление локальную транзакцию.
                    to_delete.append(local_transaction)
                    if local_transaction.balance_id:
                        self._irrelevant_balances.add(
                            balance_id=str(local_transaction.balance_id),
                            irrelevancy_date_time=local_transaction.date_time_load
                        )

        # Удаляем помеченные транзакции из БД
        self.logger.info(f'Удалить тразакции из локальной БД: {len(to_delete)} шт')
        if len(to_delete):
            self.logger.info('Удаляю помеченные локальные транзакции из БД')

            for transaction in to_delete:
                await self.delete_object(TransactionOrm, transaction.id)

        # Транзакции от поставщика услуг, оставшиеся необработанными,
        # записываем в локальную БД.
        counter = sum(list(map(
            lambda card_number: len(remote_transactions.get(card_number)), remote_transactions
        )))
        self.logger.info(f'Новые тразакции от системы ХНП: {counter} шт')

        if counter:
            self.logger.info(
                'Начинаю обработку транзакций от системы ХНП, которые не обнаружены в локальной БД'
            )
            await self.process_new_remote_transactions(remote_transactions, transaction_repository)

        # Записываем в БД время последней успешной синхронизации
        await self.update_object(self.system, update_data={"transactions_sync_dt": datetime.now(tz=TZ)})

        # Обновляем время последней транзакции для карт
        await transaction_repository.renew_cards_date_last_use()
        # await self.renew_cards_date_last_use()

    def change_card_states(self, card_numbers_to_change_state: List[str]) -> None:
        self.parser.login()
        self.parser.change_card_states(card_numbers_to_change_state)

    async def compare_cards(self, khnp_cards: List[Dict[str, Any]], local_cards: List[CardOrm]) -> None:
        """
        Сравниваем карты локальные с полученными от системы.
        Создаем в локальной БД карты, которые есть у системы, но нет локально.
        """
        # Тип карты по умолчанию
        stmt = sa_select(CardTypeOrm).where(CardTypeOrm.name == 'Пластиковая карта')
        default_card_type = await self.select_first(stmt)

        # Сравниваем карты из системы с локальными.
        # В локальной БД создаем новые, если появились в системе.
        # В локальной БД обновляем статус карт на тот, который установлен в системе.
        new_local_cards = []
        local_cards_to_change_status = []
        for khnp_card in khnp_cards:
            local_card = self.get_equal_local_card(khnp_card, local_cards)
            khnp_card_status = self.parser.get_card_state(khnp_card["cardNo"])
            if khnp_card_status in [CardStatus.ACTIVE, CardStatus.ACTIVATE_PENDING]:
                khnp_card_status_is_active = True
            else:
                khnp_card_status_is_active = False

            if local_card:
                # В локальной системе есть соответствующая карта - сверяем статусы
                if khnp_card_status_is_active != local_card:
                    local_card.is_active = khnp_card_status_is_active
                    local_cards_to_change_status.append({"id": local_card.id, "is_active": local_card.is_active})

            else:
                # В локальной системе нет такой карты - создаем её
                new_local_cards.append({
                    "card_number": khnp_card["cardNo"],
                    "card_type_id": default_card_type.id,
                    "is_active": True,
                })

        # Обновляем в БД статусы карт
        if local_cards_to_change_status:
            await self.bulk_update(CardOrm, local_cards_to_change_status)

        # Записываем в БД сведения о новых картах
        if new_local_cards:
            await self.bulk_insert_or_update(CardOrm, new_local_cards, index_field="card_number")

            # Получаем список созданных карт и привязываем их к системе
            new_card_numbers = [card["card_number"] for card in new_local_cards]
            stmt = sa_select(CardOrm).where(CardOrm.card_number.in_(new_card_numbers))
            new_local_cards = await self.select_all(stmt)
            card_system_bindings = [{"card_id": card.id, "system_id": self.system.id} for card in new_local_cards]
            await self.bulk_insert_or_update(CardSystemOrm, card_system_bindings)
            self.logger.info(f"Импортировано {len(new_local_cards)} новых карт")

    async def set_card_states(self, company_ids_to_change_card_states: Dict[str, List[str]]):
        await self.init_system()

        remote_cards = self.get_khnp_cards()

        # Получаем из локальной БД карты, принадлежащие системе ХНП
        card_repository = CardRepository(self.session, None)
        # local_cards = await card_repository.get_cards_by_system_id(self.system.id)

        local_cards_to_be_active = await card_repository.get_cards_by_filters(
            balance_ids=company_ids_to_change_card_states["to_activate"],
            system_id=self.system.id
        )

        local_cards_to_be_blocked = await card_repository.get_cards_by_filters(
            balance_ids=company_ids_to_change_card_states["to_block"],
            system_id=self.system.id
        )

        # Устанавливаем статусы карт без сохранения в БД
        for card in local_cards_to_be_active:
            card.is_active = True
            card.reason_for_blocking = None

        for card in local_cards_to_be_blocked:
            card.is_active = False
            card.reason_for_blocking = BlockingCardReason.NNK

        # Сверяем статусы карт локально и в системе
        remote_cards_to_change_state, local_cards = self.compare_khnp_card_states(
            remote_cards=remote_cards,
            local_cards_to_be_active=local_cards_to_be_active,
            local_cards_to_be_blocked=local_cards_to_be_blocked
        )

        # Устанавливаем статусы карт локально с сохранением в БД - после процедуры сравнения статусы погли измениться
        self.logger.info("Обновляю статусы карт в локальной БД")
        dataset = [
            {
                "id": card.id,
                "is_active": card.is_active,
                "reason_for_blocking": card.reason_for_blocking
            } for card in local_cards
        ]
        await self.bulk_update(CardOrm, dataset)

        # Устанавливаем статусы карт в ХНП
        self.logger.info("Обновляю статусы карт в ХНП")
        self.change_card_states(remote_cards_to_change_state)

    """
    @staticmethod
    def _filter_system_cards(cards: List[CardOrm], filter_system: SystemOrm) -> List[CardOrm]:
        system_cards = []
        for card in cards:
            for system in card.systems:
                if system.id == filter_system.id:
                    system_cards.append(card)

        return system_cards
    """

    @staticmethod
    def compare_khnp_card_states(remote_cards: List[Dict[str, Any]], local_cards_to_be_active: List[CardOrm],
                                 local_cards_to_be_blocked: List[CardOrm]) -> Tuple[List[str], List[CardOrm]]:
        khnp_cards_to_change_state = []
        # Активные карты
        for local_card in local_cards_to_be_active:
            for remote_card in remote_cards:
                if remote_card["cardNo"] == local_card.card_number:
                    # В ХНП карта заблокирована по ПИН
                    if remote_card["status_name"] == "Заблокирована по ПИН":
                        local_card.is_active = False
                        local_card.reason_for_blocking = BlockingCardReason.PIN

                    # В ХНП карта заблокирована или помечена на блокировку
                    elif remote_card["cardBlockRequest"] in [CardStatus.BLOCKING_PENDING.value,
                                                             CardStatus.BLOCKED.value]:
                        if remote_card["status_name"] == "Активная":
                            khnp_cards_to_change_state.append(local_card.card_number)
                            local_card.reason_for_blocking = BlockingCardReason.NNK

                    break

        # Заблокированные карты: ручная блокировка
        for local_card in local_cards_to_be_blocked:
            if local_card.reason_for_blocking in [BlockingCardReason.NNK, None]:
                if local_card.reason_for_blocking is None:
                    local_card.reason_for_blocking = BlockingCardReason.NNK

                for remote_card in remote_cards:
                    if remote_card["cardNo"] == local_card.card_number:
                        # В ХНП карта заблокирована по ПИН
                        if remote_card["status_name"] == "Заблокирована по ПИН":
                            local_card.is_active = False
                            local_card.reason_for_blocking = BlockingCardReason.PIN

                        # В ХНП карта разблокирована или помечена на разблокировку
                        elif remote_card["cardBlockRequest"] in [CardStatus.ACTIVE.value,
                                                                 CardStatus.ACTIVATE_PENDING.value]:
                            khnp_cards_to_change_state.append(local_card.card_number)

                        break

        # Заблокированные карты: блокировка по ПИН
        for local_card in local_cards_to_be_blocked:
            if local_card.reason_for_blocking == BlockingCardReason.PIN:
                for remote_card in remote_cards:
                    if remote_card["cardNo"] == local_card.card_number:
                        if remote_card["status_name"] == "Активная":
                            if remote_card["cardBlockRequest"] in [CardStatus.ACTIVE.value,
                                                                   CardStatus.BLOCKING_PENDING.value]:
                                local_card.is_active = True
                                local_card.reason_for_blocking = None

                            if remote_card["cardBlockRequest"] == CardStatus.BLOCKING_PENDING.value:
                                khnp_cards_to_change_state.append(local_card.card_number)

                            if remote_card["cardBlockRequest"] == CardStatus.BLOCKED.value:
                                local_card.is_active = False
                                local_card.reason_for_blocking = BlockingCardReason.NNK

                            if remote_card["cardBlockRequest"] == CardStatus.ACTIVATE_PENDING.value:
                                local_card.is_active = True
                                local_card.reason_for_blocking = None

                        elif remote_card["status_name"] == "Заблокирована по ПИН":
                            if remote_card["cardBlockRequest"] == CardStatus.ACTIVATE_PENDING.value:
                                khnp_cards_to_change_state.append(local_card.card_number)

                        break

        local_cards: List[CardOrm] = local_cards_to_be_active + local_cards_to_be_blocked
        return khnp_cards_to_change_state, local_cards
