from datetime import date, timedelta
from typing import List

from src.database import models
from src.repositories.transaction import TransactionRepository


class TransactionService:

    def __init__(self, repository: TransactionRepository) -> None:
        self.repository = repository
        self.logger = repository.logger

    async def get_transactions(self, end_date: date) -> List[models.Transaction]:
        start_date = end_date - timedelta(days=30)
        end_date = end_date + timedelta(days=1)
        transactions = await self.repository.get_transactions(start_date, end_date)
        return transactions
