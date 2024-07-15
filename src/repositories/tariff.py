from datetime import date
from typing import List, Optional

from sqlalchemy import select as sa_select, func as sa_func, and_, or_, null
from sqlalchemy.orm import joinedload, aliased

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
        """
        stmt = (
            sa_select(models.Tariff, sa_func.count(models.Company.id).label('companies_amount'))
            .select_from(models.Company)
            .group_by(models.Tariff)
            .order_by(models.Tariff.name)
        )
        dataset = await self.select_all(stmt, scalars=False)
        tariffs = list(map(lambda data: data[0].annotate({'companies_amount': data[1]}), dataset))
        """
        stmt = (
            sa_select(models.Tariff)
            .order_by(models.Tariff.name)
        )
        tariffs = await self.select_all(stmt)
        return tariffs

    async def get_companies_amount(self, tariff_id: str) -> int:
        stmt = (
            sa_select(sa_func.count(models.Company.id))
            .where(models.Company.tariff_id == tariff_id)
        )
        amount = await self.select_single_field(stmt)
        return amount

    async def get_tariff_on_date(self, balance_id: str, system_id: str, date_: date) -> models.Tariff:
        # Получаем историю применения тарифов для найденной организации
        bth = aliased(models.BalanceTariffHistory, name="bth")
        stmt = (
            sa_select(models.Tariff)
            .join(bth, and_(
                bth.balance_id == balance_id,
                bth.system_id == system_id,
                bth.start_date <= date_,
                or_(
                    bth.end_date > date_,
                    bth.end_date.is_(null())
                )
            ))
        )
        tariff = await self.select_first(stmt)

        # Если в истории никаких записей не найдено, то возвращаем текущий тариф
        if not tariff:
            bst = aliased(models.BalanceSystemTariff, name="bst")
            stmt = (
                sa_select(models.Tariff)
                .join(bst, and_(
                    bst.balance_id == balance_id,
                    bst.system_id == system_id
                ))
            )
            tariff = await self.select_first(stmt)

        return tariff
