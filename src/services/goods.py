from typing import List

from src.database import models
from src.repositories.goods import GoodsRepository
from src.schemas.goods import OuterGoodsReadSchema, InnerGoodsEditSchema
from src.schemas.system import SystemReadMinimumSchema
from src.utils.exceptions import BadRequestException


class GoodsService:

    def __init__(self, repository: GoodsRepository) -> None:
        self.repository = repository
        self.logger = repository.logger

    async def get_all_goods(self) -> List[OuterGoodsReadSchema]:
        goods = await self.repository.get_all_goods()

        def get_schema(goods_obj: models.OuterGoods):
            system_schema = SystemReadMinimumSchema(**goods_obj.system.dumps())
            goods_schema = OuterGoodsReadSchema(
                id=goods_obj.id,
                outer_name=goods_obj.name,
                inner_name=goods_obj.inner_goods.name,
                system=system_schema
            )
            return goods_schema

        goods = list(map(get_schema, goods))
        return goods

    async def get_all_inner_goods(self) -> List[models.InnerGoods]:
        goods = await self.repository.get_all_inner_goods()
        return goods

    async def get_single_goods(self, outer_goods_id: str) -> OuterGoodsReadSchema:
        goods = await self.repository.get_single_goods(outer_goods_id)
        system_schema = SystemReadMinimumSchema(**goods.system.dumps())
        goods_schema = OuterGoodsReadSchema(
            id=goods.id,
            outer_name=goods.name,
            inner_name=goods.inner_goods.name,
            system=system_schema
        )
        return goods_schema

    async def edit(self, outer_goods_id: str, data: InnerGoodsEditSchema) -> OuterGoodsReadSchema:
        # Получаем запись из БД
        outer_goods = await self.repository.get_single_goods(outer_goods_id)
        if not outer_goods:
            raise BadRequestException('Запись не найдена')

        # Ищем inner_goods с наименованием, соответствующем полученному
        inner_goods = await self.repository.get_single_inner_goods_by_name(data.inner_name)

        # Если не найден, то создаем новый
        if not inner_goods:
            inner_goods = await self.repository.create_inner_goods(data.inner_name)

        await self.repository.update_object(inner_goods, {"name": data.inner_name})

        # Формируем ответ
        outer_goods = await self.get_single_goods(outer_goods.id)
        return outer_goods
