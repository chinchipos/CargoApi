from datetime import datetime
from typing import List, Dict

from sqlalchemy import select as sa_select, null, nullslast
from sqlalchemy.orm import joinedload, contains_eager

from src.database.models import SystemOrm, RegionOrm
from src.database.models.azs import AzsOwnType, AzsOrm
from src.database.models.goods_category import GoodsCategory
from src.database.models.tariff import TariffPolicyOrm, TariffNewOrm
from src.repositories.azs import AzsRepository
from src.repositories.base import BaseRepository


class TariffRepository(BaseRepository):

    """
    async def create(self, tariff_create_schema: TariffCreateSchema) -> TariffOrm:
        new_tariff = TariffOrm(**tariff_create_schema.model_dump())
        await self.save_object(new_tariff)
        await self.session.refresh(new_tariff)

        return new_tariff
    """
    """
    async def get_tariffs(self) -> List[TariffOrm]:
        stmt = (
            sa_select(TariffOrm)
            .order_by(TariffOrm.name)
        )
        tariffs = await self.select_all(stmt)
        return tariffs
    """

    async def get_tariffs(self, system_id: str = None) -> List[TariffNewOrm]:
        stmt = (
            sa_select(TariffNewOrm)
            .order_by(
                TariffNewOrm.policy_id,
                TariffNewOrm.system_id,
                nullslast(TariffNewOrm.azs_own_type),
                nullslast(TariffNewOrm.region_id),
                nullslast(TariffNewOrm.azs_id),
                nullslast(TariffNewOrm.inner_goods_category),
                nullslast(TariffNewOrm.inner_goods_group_id)
            )
        )
        if system_id:
            stmt = stmt.where(TariffNewOrm.system_id == system_id)

        tariffs = await self.select_all(stmt)
        return tariffs

    async def get_tariff_polices_without_tariffs(self) -> List[TariffPolicyOrm]:
        stmt = (
            sa_select(TariffPolicyOrm)
            .order_by(TariffPolicyOrm.is_active, TariffPolicyOrm.name)
        )

        polices = await self.select_all(stmt)
        return polices

    async def get_tariff_polices(self, filters: Dict[str, str] = None) -> List[TariffPolicyOrm]:
        if filters is None:
            filters = {}

        stmt = (
            sa_select(TariffPolicyOrm)
            .outerjoin(TariffNewOrm)
            .options(
                contains_eager(TariffPolicyOrm.tariffs)
                .options(
                    joinedload(TariffNewOrm.system)
                    .load_only(SystemOrm.id, SystemOrm.full_name, SystemOrm.short_name)
                )
                .options(
                    joinedload(TariffNewOrm.inner_goods_group)
                )
                .options(
                    joinedload(TariffNewOrm.azs)
                    .joinedload(AzsOrm.system)
                )
                .options(
                    joinedload(TariffNewOrm.region)
                )
            )
            .where(TariffNewOrm.end_time.is_(null()))
            .order_by(
                TariffPolicyOrm.is_active,
                TariffPolicyOrm.name,
                TariffNewOrm.system_id,
                nullslast(TariffNewOrm.azs_own_type),
                nullslast(TariffNewOrm.region_id),
                nullslast(TariffNewOrm.azs_id),
                nullslast(TariffNewOrm.inner_goods_category),
                nullslast(TariffNewOrm.inner_goods_group_id)
            )
        )

        if filters.get("policy_id", None):
            stmt = stmt.where(TariffPolicyOrm.id == filters["policy_id"])

        if filters.get("system_id", None):
            stmt = stmt.where(TariffNewOrm.system_id == filters["system_id"])

        if filters.get("azs_id", None):
            stmt = stmt.where(TariffNewOrm.azs_id == filters["azs_id"])

        if filters.get("azs_own_type_id", None):
            stmt = stmt.where(TariffNewOrm.azs_own_type == filters["azs_own_type_id"])

        if filters.get("region_id", None):
            stmt = stmt.where(TariffNewOrm.region_id == filters["region_id"])

        if filters.get("category_id", None):
            stmt = stmt.where(TariffNewOrm.inner_goods_category == filters["category_id"])

        if filters.get("group_id", None):
            stmt = stmt.where(TariffNewOrm.inner_goods_group_id == filters["group_id"])

        azs_repository = AzsRepository(session=self.session)
        polices: List[TariffPolicyOrm] = await self.select_all(stmt)
        for policy in polices:
            for tariff in policy.tariffs:
                if tariff.azs:
                    pretty_address = azs_repository.pretty_address(
                        addr_json=tariff.azs.address,
                        system_short_name=tariff.azs.system.short_name if tariff.system else None
                    )
                    tariff.azs.annotate({"pretty_address": pretty_address})

        return polices

    async def create_tariff_policy(self, policy_name: str, is_active: bool = True) -> TariffPolicyOrm:
        policy = TariffPolicyOrm(name=policy_name, is_active=is_active)
        await self.save_object(policy)
        return policy

    async def get_tariff_policy(self, policy_id: str, with_arch_tariffs: bool = False) -> TariffPolicyOrm:
        stmt = (
            sa_select(TariffPolicyOrm)
            .outerjoin(TariffNewOrm)
            .options(
                contains_eager(TariffPolicyOrm.tariffs)
            )
            .where(TariffPolicyOrm.id == policy_id)
        )
        if not with_arch_tariffs:
            stmt = stmt.where(TariffNewOrm.end_time.is_(null()))

        policy = await self.select_first(stmt)
        return policy

    async def create_tariff(self, policy_id: str, system_id: str, azs_own_type: AzsOwnType, region_id: str,
                            azs_id: str, goods_group_id: str, goods_category: GoodsCategory,  discount_fee: float,
                            begin_time: datetime) -> TariffNewOrm:
        tariff = TariffNewOrm(
            policy_id=policy_id,
            system_id=system_id,
            azs_own_type=azs_own_type,
            region_id=region_id,
            azs_id=azs_id,
            inner_goods_group_id=goods_group_id,
            inner_goods_category=goods_category,
            discount_fee=discount_fee,
            begin_time=begin_time
        )
        await self.save_object(tariff)
        return tariff

    async def get_regions(self) -> List[RegionOrm]:
        stmt = sa_select(RegionOrm).order_by(RegionOrm.country, RegionOrm.name)
        regions = await self.select_all(stmt)
        return regions

    async def get_azs_stations(self, system_id: str = None) -> List[AzsOrm]:
        stmt = (
            sa_select(AzsOrm)
            .options(
                joinedload(AzsOrm.region)
            )
        )
        if system_id:
            stmt = stmt.where(AzsOrm.system_id == system_id)

        azs_stations = await self.select_all(stmt)
        return azs_stations
