from typing import List, Dict, Any

from sqlalchemy import select as sa_select, nulls_first
from sqlalchemy.orm import joinedload, selectinload

from src.database.models import OuterGoodsGroupOrm, InnerGoodsGroupOrm
from src.database.models.goods_category import OuterGoodsCategoryOrm, GoodsCategory
from src.database.models.goods import OuterGoodsOrm, InnerGoodsOrm
from src.repositories.base import BaseRepository


class GoodsRepository(BaseRepository):
    async def get_outer_goods(self, limit: int | None = None) -> List[OuterGoodsOrm]:
        stmt = (
            sa_select(OuterGoodsOrm)
            .options(
                joinedload(OuterGoodsOrm.system)
            )
            .options(
                joinedload(OuterGoodsOrm.inner_goods)
                .joinedload(InnerGoodsOrm.inner_group)
            )
            .options(
                joinedload(OuterGoodsOrm.outer_group)
                .joinedload(OuterGoodsGroupOrm.outer_category)
            )
            .outerjoin(InnerGoodsOrm)
            .order_by(nulls_first(InnerGoodsOrm.name), OuterGoodsOrm.name)
        )
        if limit:
            stmt = stmt.limit(limit)

        goods = await self.select_all(stmt)
        return goods

    async def get_all_inner_goods(self) -> List[InnerGoodsOrm]:
        stmt = sa_select(InnerGoodsOrm).order_by(InnerGoodsOrm.name)
        goods = await self.select_all(stmt)
        return goods

    async def get_single_goods(self, outer_goods_id: str) -> OuterGoodsOrm:
        stmt = (
            sa_select(OuterGoodsOrm)
            .options(
                joinedload(OuterGoodsOrm.system),
                joinedload(OuterGoodsOrm.inner_goods)
            )
            .where(OuterGoodsOrm.id == outer_goods_id)
            .order_by(OuterGoodsOrm.name)
        )
        goods = await self.select_first(stmt)
        return goods

    async def get_single_inner_goods_by_name(self, inner_name: str) -> InnerGoodsOrm:
        stmt = sa_select(InnerGoodsOrm).where(InnerGoodsOrm.name == inner_name)
        inner_goods = await self.select_first(stmt)
        return inner_goods

    async def create_inner_goods(self, inner_name: str) -> InnerGoodsOrm:
        inner_goods = await self.insert_or_update(InnerGoodsOrm, 'name', name=inner_name)
        return inner_goods

    async def get_outer_categories(self, system_id: str | None = None) -> List[OuterGoodsCategoryOrm]:
        stmt = (
            sa_select(OuterGoodsCategoryOrm)
            .order_by(OuterGoodsCategoryOrm.system_id, OuterGoodsCategoryOrm.name)
        )
        if system_id:
            stmt = stmt.where(OuterGoodsCategoryOrm.system_id == system_id)

        categories = await self.select_all(stmt)
        return categories

    async def get_outer_groups(self, system_id: str | None = None) -> List[OuterGoodsGroupOrm]:
        stmt = (
            sa_select(OuterGoodsGroupOrm)
            .order_by(OuterGoodsGroupOrm.system_id, OuterGoodsGroupOrm.name)
        )
        if system_id:
            stmt = stmt.where(OuterGoodsGroupOrm.system_id == system_id)

        groups = await self.select_all(stmt)
        return groups

    async def get_inner_groups(self) -> List[InnerGoodsGroupOrm]:
        stmt = (
            sa_select(InnerGoodsGroupOrm)
            .options(
                selectinload(InnerGoodsGroupOrm.outer_goods_groups)
                .joinedload(OuterGoodsGroupOrm.outer_category)
            )
            .order_by(InnerGoodsGroupOrm.name)
        )
        groups = await self.select_all(stmt)
        return groups

    async def get_categories_dictionary(self) -> List[Dict[str, Any]]:
        inner_groups = await self.get_inner_groups()

        categories = [
            {
                "id": category.name,
                "name": category.value,
                "groups": [group for group in inner_groups if group.inner_category == category]
            } for category in GoodsCategory
        ]

        return categories
