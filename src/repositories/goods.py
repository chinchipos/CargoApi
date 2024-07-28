from typing import List

from sqlalchemy import select as sa_select, nulls_first
from sqlalchemy.orm import joinedload

from src.database.model import models
from src.repositories.base import BaseRepository


class GoodsRepository(BaseRepository):
    async def get_all_outer_goods(self) -> List[models.OuterGoods]:
        stmt = (
            sa_select(models.OuterGoods)
            .options(
                joinedload(models.OuterGoods.system),
                joinedload(models.OuterGoods.inner_goods)
            )
            .outerjoin(models.InnerGoods)
            .order_by(nulls_first(models.InnerGoods.name), models.OuterGoods.name)
        )
        goods = await self.select_all(stmt)
        return goods

    async def get_all_inner_goods(self) -> List[models.InnerGoods]:
        stmt = sa_select(models.InnerGoods).order_by(models.InnerGoods.name)
        goods = await self.select_all(stmt)
        return goods

    async def get_single_goods(self, outer_goods_id: str) -> models.OuterGoods:
        stmt = (
            sa_select(models.OuterGoods)
            .options(
                joinedload(models.OuterGoods.system),
                joinedload(models.OuterGoods.inner_goods)
            )
            .where(models.OuterGoods.id == outer_goods_id)
            .order_by(models.OuterGoods.name)
        )
        goods = await self.select_first(stmt)
        return goods

    async def get_single_inner_goods_by_name(self, inner_name: str) -> models.InnerGoods:
        stmt = sa_select(models.InnerGoods).where(models.InnerGoods.name == inner_name)
        inner_goods = await self.select_first(stmt)
        return inner_goods

    async def create_inner_goods(self, inner_name: str) -> models.InnerGoods:
        inner_goods = await self.insert_or_update(models.InnerGoods, 'name', name=inner_name)
        return inner_goods
