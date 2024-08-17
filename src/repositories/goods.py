from typing import List

from sqlalchemy import select as sa_select, nulls_first
from sqlalchemy.orm import joinedload

from src.database.model.goods import OuterGoodsOrm, InnerGoodsOrm
from src.repositories.base import BaseRepository


class GoodsRepository(BaseRepository):
    async def get_all_outer_goods(self) -> List[OuterGoodsOrm]:
        stmt = (
            sa_select(OuterGoodsOrm)
            .options(
                joinedload(OuterGoodsOrm.system),
                joinedload(OuterGoodsOrm.inner_goods)
            )
            .outerjoin(InnerGoodsOrm)
            .order_by(nulls_first(InnerGoodsOrm.name), OuterGoodsOrm.name)
        )
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
