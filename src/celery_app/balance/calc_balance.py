from datetime import datetime
from typing import List, Dict

from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.celery_app.irrelevant_balances import IrrelevantBalances
from src.database.models.transaction import TransactionOrm
from src.database.models.balance import BalanceOrm
from src.repositories.base import BaseRepository
from src.utils.enums import ContractScheme
from src.utils.loggers import get_logger


class CalcBalances(BaseRepository):

    def __init__(self, session: AsyncSession):
        super().__init__(session=session, user=None)
        self.logger = get_logger(name="CALC_BALANCES", filename="celery.log")

    async def calculate(self, irrelevant_balances: IrrelevantBalances) -> Dict[str, List[str]]:
        balances_dataset = []
        for balance_id, from_date_time in irrelevant_balances['irrelevant_balances'].items():
            # Вычисляем и устанавливаем балансы в истории транзакций
            company_balance = await self.calculate_transaction_balances(balance_id, from_date_time)
            balances_dataset.append({"id": balance_id, "balance": company_balance})

        # Обновляем текущие балансы
        self.logger.info('Обновляю текущие значения балансов')
        await self.bulk_update(BalanceOrm, balances_dataset)

        # Вычисляем каким организациям нужно заблокировать карты, а каким разблокировать
        balance_ids_to_change_card_states = await self.calc_card_states()

        return balance_ids_to_change_card_states

    async def get_initial_transaction(self, balance_id: str, from_date_time: datetime) -> TransactionOrm:
        stmt = (
            sa_select(TransactionOrm)
            .where(TransactionOrm.balance_id == balance_id)
            .where(TransactionOrm.date_time_load < from_date_time)
            .order_by(TransactionOrm.date_time_load.desc())
            .limit(1)
        )
        # self.statement(stmt)
        transaction = await self.select_first(stmt)
        return transaction

    async def get_transactions_to_recalculate(self, balance_id: str, from_date_time: datetime) -> List[TransactionOrm]:
        stmt = (
            sa_select(TransactionOrm)
            .options(
                joinedload(TransactionOrm.balance)
                .joinedload(BalanceOrm.company)
            )
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
        for transaction in transactions_to_recalculate:
            transaction.company_balance = previous_transaction.company_balance + transaction.total_sum \
                if previous_transaction else transaction.total_sum

            previous_transaction = transaction

        # Сохраняем в БД
        dataset = []
        for transaction in transactions_to_recalculate:
            dataset.append({
                'id': transaction.id,
                'company_balance_after': transaction.company_balance,
            })
            await self.bulk_update(TransactionOrm, dataset)

        last_balance = previous_transaction.company_balance if previous_transaction else 0
        return last_balance

    async def calc_card_states(self) -> Dict[str, List[str]]:
        # Получаем все перекупные балансы
        stmt = (
            sa_select(BalanceOrm)
            .options(
                joinedload(BalanceOrm.company)
            )
            .where(BalanceOrm.scheme == ContractScheme.OVERBOUGHT)
        )
        balances = await self.select_all(stmt)

        # Анализируем настройки организации и текущий баланс, делаем заключение о том,
        # какое состояние карт у этой организации должно быть
        balance_ids_to_block_cards = set()
        balance_ids_to_activate_cards = set()
        for balance in balances:
            # Получаем размер овердрафта
            overdraft_sum = balance.company.overdraft_sum if balance.company.overdraft_on else 0
            if overdraft_sum > 0:
                overdraft_sum = -overdraft_sum

            # Получаем порог баланса, ниже которого требуется блокировка карт
            boundary = balance.company.min_balance + overdraft_sum

            if balance.balance < boundary:
                # Делаем пометку о том, что у этой организации карты должны находиться в заблокированном состоянии
                balance_ids_to_block_cards.add(balance.id)

            else:
                # Делаем пометку о том, что у этой организации карты должны находиться в разблокированном состоянии
                balance_ids_to_activate_cards.add(balance.id)

        balance_ids_to_change_card_states = dict(
            to_block = list(balance_ids_to_block_cards),
            to_activate = list(balance_ids_to_activate_cards)
        )
        return balance_ids_to_change_card_states
