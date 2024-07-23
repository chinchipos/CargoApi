from datetime import datetime
from typing import List

from sqlalchemy import select as sa_select

from src.connectors.irrelevant_balances import IrrelevantBalances
from src.database.models import Transaction as TransactionOrm, Balance as BalanceOrm
from src.repositories.base import BaseRepository
from src.utils.log import ColoredLogger


class CalcBalances(BaseRepository):

    async def get_initial_transaction(self, balance_id: str, from_date_time: datetime) -> TransactionOrm:
        stmt = (
            sa_select(TransactionOrm)
            .where(TransactionOrm.balance_id == balance_id)
            .where(TransactionOrm.date_time_load < from_date_time)
            .order_by(TransactionOrm.date_time_load.desc())
            .limit(1)
        )
        transaction = await self.select_first(stmt)
        return transaction

    async def get_transactions_to_recalculate(self, balance_id: str, from_date_time: datetime) -> List[TransactionOrm]:
        stmt = (
            sa_select(TransactionOrm)
            .where(TransactionOrm.balance_id == balance_id)
            .where(TransactionOrm.date_time_load >= from_date_time)
            .order_by(TransactionOrm.date_time_load)
        )
        transactions = await self.select_all(stmt)
        return transactions

    async def calculate_transaction_balances(self, balance_id: str, from_date_time: datetime) -> float:
        # Получаем транзакцию компании, которая предшествует указанному времени
        initial_transaction = await self.get_initial_transaction(balance_id, from_date_time)

        # Получаем все транзакции компании по указанному балансу, начиная с указанного времени
        transactions_to_recalculate = await self.get_transactions_to_recalculate(balance_id, from_date_time)

        # Пересчитываем балансы
        previous_transaction = initial_transaction
        previous_company_balance = previous_transaction.company_balance if previous_transaction else 0
        for transaction in transactions_to_recalculate:
            transaction.company_balance = previous_company_balance + transaction.total_sum
            previous_company_balance = float(transaction.company_balance)

        # Сохраняем в БД
        dataset = []
        for transaction in transactions_to_recalculate:
            dataset.append({
                'id': transaction.id,
                'company_balance_after': transaction.company_balance,
            })
            await self.bulk_update(TransactionOrm, dataset)

        return previous_company_balance

    async def calculate(self, irrelevant_balances: IrrelevantBalances, logger: ColoredLogger) -> None:
        balances_dataset = []
        for balance_id, from_date_time in irrelevant_balances['data'].items():
            # Вычисляем и устанавливаем балансы в истории транзакций
            company_balance = await self.calculate_transaction_balances(balance_id, from_date_time)
            balances_dataset.append({"id": balance_id, "balance": company_balance})

        # Обновляем текущие балансы
        logger.info('Обновляю текущие значения балансов')
        await self.bulk_update(BalanceOrm, balances_dataset)
