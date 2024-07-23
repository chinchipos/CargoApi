from datetime import date, timedelta
from typing import List

from src.database.models import Transaction as TransactionOrm
from src.repositories.transaction import TransactionRepository


class TransactionService:

    def __init__(self, repository: TransactionRepository) -> None:
        self.repository = repository
        self.logger = repository.logger

    async def get_transactions(self, end_date: date) -> List[TransactionOrm]:
        start_date = end_date - timedelta(days=50)
        end_date = end_date + timedelta(days=1)
        transactions = await self.repository.get_transactions(start_date, end_date)
        return transactions
