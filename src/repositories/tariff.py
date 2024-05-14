from typing import List

from sqlalchemy import select as sa_select, func as sa_func
from sqlalchemy.exc import IntegrityError

from src.database import models
from src.repositories.base import BaseRepository
from src.schemas.tariff import TariffCreateSchema
from src.utils.exceptions import DBDuplicateException


class TariffRepository(BaseRepository):

    async def create(self, tariff: TariffCreateSchema) -> models.Tariff:
        try:
            new_tariff = models.Tariff(**tariff.model_dump())
            self.session.add(new_tariff)
            await self.session.flush()
            await self.session.commit()
            await self.session.refresh(new_tariff)

        except IntegrityError:
            raise DBDuplicateException()

        return new_tariff

    async def get_tariffs(self) -> List[models.Tariff]:
        stmt = (
            sa_select(models.Tariff, sa_func.count(models.Company.id).label('companies_amount'))
            .select_from(models.Company)
            .outerjoin(models.Tariff.companies)
            .group_by(models.Tariff)
            .order_by(models.Tariff.name)
        )
        dataset = await self.select_all(stmt, scalars=False)
        tariffs = list(map(lambda data: data[0].annotate({'companies_amount': data[1]}), dataset))
        return tariffs

    async def get_companies_amount(self, tariff_id: str) -> int:
        stmt = (
            sa_select(sa_func.count(models.Company.id))
            .where(models.Company.tariff_id == tariff_id)
        )
        amount = await self.select_single_field(stmt)
        return amount
