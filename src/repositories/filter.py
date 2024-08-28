from typing import List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select as sa_select
from sqlalchemy.orm import load_only

from src.database.models import CompanyOrm
from src.database.models.user import UserOrm
from src.repositories.base import BaseRepository


class FilterRepository(BaseRepository):

    def __init__(self, session: AsyncSession, user: UserOrm | None = None):
        super().__init__(session, user)

    async def get_companies(self) -> List[CompanyOrm]:
        stmt = (
            sa_select(CompanyOrm)
            .options(
                load_only(
                    CompanyOrm.id,
                    CompanyOrm.name,
                    CompanyOrm.inn,
                    CompanyOrm.personal_account
                )
            )
            .order_by(CompanyOrm.name)
        )
        companies = await self.select_all(stmt)
        return companies
