from datetime import timedelta, datetime
from typing import List

from dateutil.relativedelta import relativedelta

from src.config import TZ
from src.database.model.models import Transaction as TransactionOrm
from src.repositories.transaction import TransactionRepository


class TransactionService:

    def __init__(self, repository: TransactionRepository) -> None:
        self.repository = repository
        self.logger = repository.logger

    async def get_transactions(self, company_id: str | None, from_dt: datetime | None, to_dt: datetime | None) \
            -> List[TransactionOrm]:
        if not from_dt:
            from_dt = datetime.now(tz=TZ).date() - relativedelta(months = 3 if company_id else 1)

        if not to_dt:
            to_dt = datetime.now(tz=TZ).date() + timedelta(days=1)

        transactions = await self.repository.get_transactions(company_id, from_dt, to_dt)
        return transactions
