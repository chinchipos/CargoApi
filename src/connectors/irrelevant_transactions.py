from datetime import date
from typing import Dict, List

from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from src.connectors.daily_transactions import DailyTransactions
from src.connectors.irrelevant_balances import IrrelevantBalances
from src.connectors.wrapped_transaction import WrappedTransaction
from src.database.models import Transaction as TransactionOrm
from src.repositories.base import BaseRepository
from src.utils.log import ColoredLogger

balance_id_type = str


class IrrelevantTransactions(BaseRepository):

    def __init__(self, session: AsyncSession):
        super().__init__(session=session, user=None)
        self.logger = ColoredLogger(logfile_name='schedule.log', logger_name='OVERDRAFT')
        self._irrelevant_balances = None

        # Описываем структуру данных
        # self._transactions = {
        #     balance_id: {
        #         date: [
        #             TransactionWrapper1,
        #             TransactionWrapper2
        #         ]
        #     }
        # }
        self._data: Dict[balance_id_type, DailyTransactions] = {}

    async def make_structure(self, irrelevant_balances: IrrelevantBalances) -> None:
        # По каждому балансу получаем из БД последнюю релевантную транзакцию, предшествующую дате, в которую
        # зарегистрирована первая нерелевантная транзакция.
        last_relevant_transactions = await self._get_last_relevant_transactions(irrelevant_balances)

        # По каждому балансу получаем из БД все транзакции, начиная с даты, в которую зарегистрирована первая
        # нерелевантная транзакция по этому балансу
        irrelevant_transactions = await self._get_irrelevant_transactions(last_relevant_transactions)

        for balance_id, ir_transactions in irrelevant_transactions:
            initial_relevant_transaction = self._get_initial_relevant_transaction(
                balance_id,
                last_relevant_transactions
            )
            self._data[balance_id] = DailyTransactions(ir_transactions, initial_relevant_transaction)

    def data(self) -> Dict[balance_id_type, DailyTransactions]:
        return self._data

    async def _get_last_relevant_transactions(self, irrelevant_balances: IrrelevantBalances) -> List[TransactionOrm]:
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

    async def _get_irrelevant_transactions(self, relevant_transactions: List[TransactionOrm]) \
            -> Dict[balance_id_type, List[WrappedTransaction]]:
        irrelevant_transactions = {}
        for relevant_transaction in relevant_transactions:
            stmt = (
                sa_select(TransactionOrm)
                .where(TransactionOrm.balance_id == relevant_transaction.balance_id)
                .where(TransactionOrm.date_time > relevant_transaction.date_time)
            )
            transactions = await self.select_all(stmt)
            irrelevant_transactions[relevant_transaction.balance_id] = [WrappedTransaction(t) for t in transactions]

        return irrelevant_transactions

    @staticmethod
    def _get_initial_relevant_transaction(balance_id: str, last_relevant_transactions: List[TransactionOrm]) \
            -> TransactionOrm:
        for transaction in last_relevant_transactions:
            if transaction.balance_id == balance_id:
                return transaction
