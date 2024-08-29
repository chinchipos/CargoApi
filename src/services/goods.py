import copy
from typing import List, Dict, Any

from src.database.models.goods import OuterGoodsOrm, InnerGoodsOrm
from src.repositories.goods import GoodsRepository
from src.schemas.goods import InnerGoodsEditSchema
from src.utils.exceptions import BadRequestException


class GoodsService:

    def __init__(self, repository: GoodsRepository) -> None:
        self.repository = repository
        self.logger = repository.logger

    async def get_all_outer_goods(self, with_dictionaries: bool) -> Dict[str, Any]:
        outer_goods = copy.deepcopy(await self.repository.get_outer_goods(limit=500))

        dictionaries = None
        if with_dictionaries:
            # Наименования продуктов в системе ННК
            inner_names = await self.repository.get_inner_goods_names()

            # Список продуктовых групп в системе ННК
            inner_groups = await self.repository.get_inner_groups()

            dictionaries = {
                "inner_names": inner_names,
                "inner_groups": inner_groups,
            }

        data = {
            "outer_goods": outer_goods,
            "dictionaries": dictionaries
        }

        return data

    async def get_all_inner_goods(self) -> List[InnerGoodsOrm]:
        goods = await self.repository.get_all_inner_goods()
        return goods

    async def get_single_goods(self, outer_goods_id: str) -> OuterGoodsOrm:
        goods = await self.repository.get_outer_goods_item(outer_goods_id)
        return goods

    async def edit(self, outer_goods_id: str, data: InnerGoodsEditSchema) -> OuterGoodsOrm:
        # Получаем запись из БД
        outer_goods = await self.repository.get_outer_goods_item(outer_goods_id)
        if not outer_goods:
            raise BadRequestException('Запись не найдена')

        if not data.inner_name:
            raise BadRequestException('Не указано наименование для системы ННК')

        if outer_goods.outer_group_id:
            if not data.inner_group_id:
                raise BadRequestException('Не указана группа продуктов для системы ННК')

            outer_goods.outer_group.inner_group_id = data.inner_group_id
            await self.repository.save_object(outer_goods.outer_group)

        outer_goods.inner_name = data.inner_name
        await self.repository.save_object(outer_goods)

        return outer_goods
