from datetime import timedelta, datetime
from typing import List

from dateutil.relativedelta import relativedelta

from src.config import TZ
from src.database.models.transaction import TransactionOrm
from src.repositories.transaction import TransactionRepository


class TransactionService:

    def __init__(self, repository: TransactionRepository) -> None:
        self.repository = repository
        self.logger = repository.logger

    async def get_transactions(self, company_id: str | None, from_dt: datetime | None, to_dt: datetime | None) \
            -> List[TransactionOrm]:
        rows_limit = 0

        if not from_dt:
            rows_limit = 500
            relative_delta = relativedelta(years = 3) if company_id else relativedelta(months=1)
            from_dt = datetime.now(tz=TZ).date() - relative_delta

        if not to_dt:
            to_dt = datetime.now(tz=TZ).date() + timedelta(days=1)

        transactions = await self.repository.get_transactions(company_id, from_dt, to_dt, rows_limit)
        return transactions
