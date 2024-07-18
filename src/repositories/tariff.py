from datetime import date
from typing import List

from sqlalchemy import select as sa_select, and_, or_, null
from sqlalchemy.orm import aliased

from src.database.models import (Tariff as TariffOrm, BalanceSystemTariff as BalanceSystemTariffOrm,
                                 BalanceTariffHistory as BalanceTariffHistoryOrm)
from src.repositories.base import BaseRepository
from src.schemas.tariff import TariffCreateSchema


class TariffRepository(BaseRepository):

    async def create(self, tariff_create_schema: TariffCreateSchema) -> TariffOrm:
        new_tariff = TariffOrm(**tariff_create_schema.model_dump())
        await self.save_object(new_tariff)
        await self.session.refresh(new_tariff)

        return new_tariff

    async def get_tariffs(self) -> List[TariffOrm]:
        stmt = (
            sa_select(TariffOrm)
            .order_by(TariffOrm.name)
        )
        tariffs = await self.select_all(stmt)
        return tariffs

    async def get_tariff_on_date(self, balance_id: str, system_id: str, date_: date) -> TariffOrm:
        # Получаем историю применения тарифов для найденной организации
        bth = aliased(BalanceTariffHistoryOrm, name="bth")
        stmt = (
            sa_select(TariffOrm)
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
            bst = aliased(BalanceSystemTariffOrm, name="bst")
            stmt = (
                sa_select(TariffOrm)
                .join(bst, and_(
                    bst.balance_id == balance_id,
                    bst.system_id == system_id
                ))
            )
            tariff = await self.select_first(stmt)

        return tariff
