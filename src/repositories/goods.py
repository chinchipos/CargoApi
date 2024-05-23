from typing import List

from sqlalchemy import select as sa_select
from sqlalchemy.orm import joinedload

from src.database import models
from src.repositories.base import BaseRepository


class GoodsRepository(BaseRepository):
    async def get_all_goods(self) -> List[models.OuterGoods]:
        stmt = (
            sa_select(models.OuterGoods)
            .options(
                joinedload(models.OuterGoods.system),
                joinedload(models.OuterGoods.inner_goods)
            )
            .order_by(models.OuterGoods.name)
        )
        goods = await self.select_all(stmt)
        return goods

    async def get_all_inner_goods(self) -> List[models.InnerGoods]:
        stmt = sa_select(models.InnerGoods).order_by(models.InnerGoods.name)
        goods = await self.select_all(stmt)
        return goods

    async def get_goods(self, outer_goods_id: str) -> models.OuterGoods:
        stmt = (
            sa_select(models.OuterGoods)
            .options(
                joinedload(models.OuterGoods.system),
                joinedload(models.OuterGoods.inner_goods)
            )
            .where(models.OuterGoods.id == outer_goods_id)
            .order_by(models.OuterGoods.name)
        )
        goods = await self.select_all(stmt)
        return goods
