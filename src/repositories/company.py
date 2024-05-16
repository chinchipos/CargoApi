from typing import List

from sqlalchemy import select as sa_select, func as sa_func
from sqlalchemy.orm import joinedload, selectinload

from src.database import models
from src.repositories.base import BaseRepository
from src.utils import enums


class CompanyRepository(BaseRepository):

    async def get_company(self, company_id: str) -> models.Company:
        # Получаем полные сведения об организации
        stmt = (
            sa_select(models.Company)
            .options(
                joinedload(models.Company.tariff),
                joinedload(models.Company.users).joinedload(models.User.role)
            )
            .filter_by(id=company_id)
            .order_by(models.Company.name)
            .limit(1)
        )
        dataset = await self.session.scalars(stmt)
        company = dataset.first()

        # Добавляем сведения о количестве карт
        stmt = sa_select(sa_func.count(models.Card.id)).filter_by(company_id=company_id)
        amount = await self.select_single_field(stmt)
        company.annotate({'cards_amount': amount})

        return company

    async def get_companies(self) -> List[models.Company]:
        # Получаем полные сведения об организациях
        stmt = (
            sa_select(models.Company, sa_func.count(models.Card.id).label('cards_amount'))
            .select_from(models.Card)
            .outerjoin(models.Company.cards)
            .group_by(models.Company)
            .order_by(models.Company.name)
            .options(
                selectinload(models.Company.tariff),
                selectinload(models.Company.users).joinedload(models.User.role)
            )
        )
        dataset = await self.select_all(stmt, scalars=False)
        companies = list(map(lambda data: data[0].annotate({'cards_amount': data[1]}), dataset))

        return companies

    async def get_drivers(self, company_id: str = None) -> models.User:
        stmt = (
            sa_select(models.User)
            .options(
                joinedload(models.User.company),
                joinedload(models.User.role),
            )
            .join(models.User.company)
            .where(models.Role.name == enums.Role.COMPANY_DRIVER.name)
            # .where(models.User.role_id == models.Role.id)
            .order_by(models.Company.name, models.User.last_name, models.User.first_name)
        )
        if company_id:
            stmt = stmt.where(models.User.company_id == company_id)

        drivers = await self.select_all(stmt)
        return drivers
