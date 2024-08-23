from datetime import date
from typing import List

from sqlalchemy import select as sa_select, and_, or_, null
from sqlalchemy.orm import aliased, selectinload, joinedload

from src.database.models import SystemOrm, AzsOrm
from src.database.models.balance_system_tariff import BalanceSystemTariffOrm
from src.database.models.balance_tariff_history import BalanceTariffHistoryOrm
from src.database.models.tariff import TariffOrm, TariffPolicyOrm, TariffNewOrm
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

    async def get_tariff_polices(self) -> List[TariffPolicyOrm]:
        stmt = (
            sa_select(TariffPolicyOrm)
            .options(
                selectinload(TariffPolicyOrm.tariffs)
                .options(
                    joinedload(TariffNewOrm.system)
                    .load_only(SystemOrm.id, SystemOrm.full_name)
                )
                .options(
                    joinedload(TariffNewOrm.inner_goods_group)
                )
                .options(
                    joinedload(TariffNewOrm.azs)
                    .load_only(
                        AzsOrm.id,
                        AzsOrm.name,
                        AzsOrm.code,
                        AzsOrm.is_active,
                        AzsOrm.country_code,
                        AzsOrm.region_code,
                        AzsOrm.address,
                        AzsOrm.is_franchisee,
                        AzsOrm.latitude,
                        AzsOrm.longitude,
                    )
                )
            )
            .order_by(TariffPolicyOrm.is_active, TariffPolicyOrm.name)
        )
        polices: List[TariffPolicyOrm] = await self.select_all(stmt)

        # Убираем архивные тарифы (не знаю как переделать запрос, поэтому такой костыль)
        for policy in polices:
            i = 0
            while i < len(policy.tariffs):
                tariff = policy.tariffs[i]
                if tariff.end_time:
                    policy.tariffs.remove(tariff)
                else:
                    i += 1

        return polices

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
