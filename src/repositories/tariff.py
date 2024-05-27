from datetime import date
from typing import List, Optional

from sqlalchemy import select as sa_select, func as sa_func
from sqlalchemy.orm import joinedload

from src.database import models
from src.repositories.base import BaseRepository
from src.schemas.tariff import TariffCreateSchema


class TariffRepository(BaseRepository):

    async def create(self, create_schema: TariffCreateSchema) -> models.Tariff:
        new_tariff = models.Tariff(**create_schema.model_dump())
        await self.save_object(new_tariff)
        await self.session.refresh(new_tariff)

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

    async def get_company_tariff_on_date(self, company: models.Company, _date_: date) -> models.Tariff:
        # Получаем историю применения тарифов для найденной организации
        stmt = (
            sa_select(models.TariffHistory)
            .options(
                joinedload(models.TariffHistory.tariff),
            )
            .where(models.TariffHistory.company_id == company.id)
            .where(models.TariffHistory.start_date <= _date_)
        )
        history = await self.select_all(stmt)

        # Выполняем поиск по записям, в которых указана дата окончания действия тарифа
        for record in history:
            if record.end_date > _date_:
                return record.tariff

        # Если существует запись без даты прекращения действия тарифа,
        # то возвращаем тариф, указанный в ней
        for record in history:
            if not record.end_date:
                return record.tariff

        # Если в истории никаких записей не найдено, то возвращаем текущий тариф организации
        return company.tariff
