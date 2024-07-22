from datetime import date
from typing import List, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select as sa_select
from sqlalchemy.orm import load_only

from src.connectors.irrelevant_balances import IrrelevantBalances
from src.repositories.base import BaseRepository

from src.database.models import (User as UserOrm, Transaction as TransactionOrm,
                                 OverdraftsHistory as OverdraftsHistoryOrm)
from src.utils.enums import TransactionType
from src.utils.log import ColoredLogger


class Overdraft(BaseRepository):

    def __init__(self, session: AsyncSession, user: UserOrm | None = None):
        super().__init__(session, user)
        self.logger = ColoredLogger(logfile_name='schedule.log', logger_name='OVERDRAFT')
        self._irrelevant_balances = IrrelevantBalances()

    async def calculate(self, irrelevant_balances: IrrelevantBalances) -> IrrelevantBalances:
        # По каждому балансу получаем из БД последнюю релевантную транзакцию за дату, предшествующую дате, в которую
        # зарегистрирована первая нерелевантная транзакция.
        last_relevant_transactions = await self.get_last_relevant_transactions(irrelevant_balances)

        # По каждому балансу получаем из БД все транзакции, начиная с даты, в которую зарегистрирована первая
        # нерелевантная транзакция по этому балансу
        irrelevant_transactions = await self.get_irrelevant_transactions(last_relevant_transactions)

        # Получаем историю овердрафтов
        overdrafts_history = await self.get_overdrafts_history(irrelevant_balances)

        # По каждому балансу циклически обрабатываем транзакции по дням:
        # 1. Проверяем наличие транзакции "Комиссия за овердрафт" - комиссия за пользование овердрафтом
        # в предыдущем дне. Если найдена и совпадает, то переходим к п.3. Если не найдена или отличается,
        # то формируем новую транзакцию или изменяем существующую (соответственно) и переходим к п.2.
        # 2. Пересчитываем транзакционные балансы за текущий день.
        # 3. Получаем последнюю транзакцию за текущий день. Если баланс на конец дня был отрицательным,
        # то формируем (но не записываем) новую транзакцию "Комиссия за овердрафт". Она пойдет в расчет
        # следующего дня.
        for balance_id, ir_transactions_list in irrelevant_transactions:
            daily_transactions = self.split_transactions_per_days(ir_transactions_list)
            calculated_overdraft_fee = 0
            for day, transactions in daily_transactions.items():
                # Проверяем в текущем дне наличие транзакции "Комиссия за овердрафт"
                stored_overdraft_fee = self.get_overdraft_fee_this_day(day, transactions)


        # Удаляем из БД лишние транзакции
        # В БД записываем новые и обновляем измененные транзакции.

        # В БД обновляем текущие остатки ДС по каждому балансу

        pass

    async def get_last_relevant_transactions(self, irrelevant_balances: IrrelevantBalances) -> List[TransactionOrm]:
        transactions = []
        for balance_id, irrelevancy_date_time in irrelevant_balances.items():
            stmt = (
                sa_select(TransactionOrm)
                .where(TransactionOrm.balance_id == balance_id)
                .where(TransactionOrm.date_time < irrelevancy_date_time.date())
                .order_by(TransactionOrm.date_time.desc())
                .limit(1)
            )
            transaction = await self.select_first(stmt)
            transactions.append(transaction)

        return transactions

    async def get_irrelevant_transactions(self, relevant_transactions: List[TransactionOrm]) \
            -> Dict[str, List[TransactionOrm]]:
        irrelevant_transactions = {}
        for relevant_transaction in relevant_transactions:
            stmt = (
                sa_select(TransactionOrm)
                .where(TransactionOrm.balance_id == relevant_transaction.balance_id)
                .where(TransactionOrm.date_time > relevant_transaction.date_time)
            )
            transactions = await self.select_all(stmt)
            irrelevant_transactions[relevant_transaction.balance_id] = transactions

        return irrelevant_transactions

    async def get_overdrafts_history(self, irrelevant_balances: IrrelevantBalances) \
            -> Dict[str, List[OverdraftsHistoryOrm]]:
        overdrafts_history = {}
        for balance_id, irrelevancy_date_time in irrelevant_balances.items():
            stmt = (
                sa_select(OverdraftsHistoryOrm)
                .where(OverdraftsHistoryOrm.balance_id == balance_id)
                .where(OverdraftsHistoryOrm.overdraft_begin_date >= irrelevancy_date_time.date())
            )
            overdraft_history = await self.select_all(stmt)
            overdrafts_history[balance_id] = overdraft_history

        return overdrafts_history

    @staticmethod
    def split_transactions_per_days(transactions: List[TransactionOrm]) -> Dict[date, List[TransactionOrm]]:
        splitted_transactions = {}
        for transaction in transactions:
            transaction_date = transaction.date_time.date()
            if transaction_date in splitted_transactions:
                splitted_transactions[transaction_date].append(transaction)
            else:
                splitted_transactions[transaction_date] = [transaction]

        return splitted_transactions

    @staticmethod
    def get_overdraft_fee_this_day(transactions: List[TransactionOrm]) -> TransactionOrm | None:
        overdraft_fee_transactions = [t for t in transactions if t.transaction_type == TransactionType.OVERDRAFT_FEE]
        # Подумать про использование класса вместо списков и словарей
        # Имеет смысл к каждой транзакции добавлять признак - что с ней делать потом: создать, обновить, удалить
