from typing import List, Any

from src.database import models
from src.repositories.base import BaseRepository

from sqlalchemy import select as sa_select, func as sa_func
from sqlalchemy.orm import joinedload, selectinload


class CompanyRepository(BaseRepository):

    async def get_company(self, company_id: str) -> models.Company:
        # Получаем полные сведения об организации
        stmt = (
            sa_select(models.Company)
            .options(
                joinedload(models.Company.tariff),
                joinedload(models.Company.users)
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
        '''
        stmt = (
            sa_select(models.Company, )
            .options(
                joinedload(models.Company.tariff),
                joinedload(models.Company.users)
            )
            .order_by(models.Company.name)
            .limit(1)
        )
        '''

        stmt = (
            sa_select(models.Company, sa_func.count(models.Card.id).label('cards_amount'))
            .select_from(models.Card)
            .outerjoin(models.Company.cards)
            .group_by(models.Company)
            .order_by(models.Company.name)
            .options(
                selectinload(models.Company.tariff),
                selectinload(models.Company.users)
            )
        )
        dataset = await self.select_all(stmt, scalars=False)
        companies = list(map(lambda data: data[0].annotate({'cards_amount': data[1]}), dataset))
        print('HHHHHHHHHHHHHHHHHHHHHHHHHHHHHH')
        print('companies:', companies)

        return companies
