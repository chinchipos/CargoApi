from typing import List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select as sa_select
from sqlalchemy.orm import load_only

from src.database.models import CompanyOrm
from src.database.models.user import UserOrm
from src.repositories.base import BaseRepository
from src.utils.enums import Role


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
        company_roles = [Role.COMPANY_ADMIN.name, Role.COMPANY_LOGIST.name, Role.COMPANY_DRIVER]
        if self.user.role.name == Role.CARGO_MANAGER.name:
            company_ids_subquery = self.user.company_ids_subquery()
            stmt = stmt.join(company_ids_subquery, company_ids_subquery.c.id == CompanyOrm.id)

        elif self.user.role.name in company_roles:
            stmt = stmt.where(CompanyOrm.id == self.user.company_id)

        companies = await self.select_all(stmt)
        return companies
