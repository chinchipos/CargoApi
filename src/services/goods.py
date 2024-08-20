from typing import List

from src.database.models.goods import OuterGoodsOrm, InnerGoodsOrm
from src.repositories.goods import GoodsRepository
from src.schemas.goods import InnerGoodsEditSchema
from src.utils.exceptions import BadRequestException


class GoodsService:

    def __init__(self, repository: GoodsRepository) -> None:
        self.repository = repository
        self.logger = repository.logger

    async def get_all_outer_goods(self) -> List[OuterGoodsOrm]:
        goods = await self.repository.get_outer_goods(limit=500)

        # def get_schema(goods_obj: models.OuterGoods):
        #     system_schema = SystemReadMinimumSchema(**goods_obj.system.dumps())
        #     goods_schema = OuterGoodsReadSchema(
        #         id=goods_obj.id,
        #         outer_name=goods_obj.name,
        #         inner_name=goods_obj.inner_goods.name if goods_obj.inner_goods_id else '',
        #         system=system_schema
        #     )
        #     return goods_schema

        # goods = list(map(get_schema, goods))
        return goods

    async def get_all_inner_goods(self) -> List[InnerGoodsOrm]:
        goods = await self.repository.get_all_inner_goods()
        return goods

    async def get_single_goods(self, outer_goods_id: str) -> OuterGoodsOrm:
        goods = await self.repository.get_single_goods(outer_goods_id)
        return goods

        # system_schema = SystemReadMinimumSchema(**goods.system.dumps())
        # goods_schema = OuterGoodsReadSchema(
        #     id=goods.id,
        #     outer_name=goods.name,
        #     inner_name=goods.inner_goods.name if goods.inner_goods_id else '',
        #     system=system_schema
        # )
        # return goods_schema

    async def edit(self, outer_goods_id: str, data: InnerGoodsEditSchema) -> OuterGoodsOrm:
        # Получаем запись из БД
        outer_goods = await self.repository.get_single_goods(outer_goods_id)
        if not outer_goods:
            raise BadRequestException('Запись не найдена')

        current_inner_goods = outer_goods.inner_goods

        # Ищем inner_goods с наименованием, соответствующим полученному
        if data.inner_name:
            new_inner_goods = await self.repository.get_single_inner_goods_by_name(data.inner_name)
            if not new_inner_goods:
                new_inner_goods = await self.repository.create_inner_goods(data.inner_name)

        else:
            new_inner_goods = None

        # Объекту outer_goods присваиваем inner_goods.
        new_inner_goods_id = new_inner_goods.id if new_inner_goods else None
        await self.repository.update_object(outer_goods, {"inner_goods_id": new_inner_goods_id})

        # Удаляем старый inner_goods, если на него не ссылаются другие объекты
        if current_inner_goods:
            await self.repository.delete_object(InnerGoodsOrm, current_inner_goods.id, silent=True)

        outer_goods = await self.get_single_goods(outer_goods.id)
        return outer_goods
