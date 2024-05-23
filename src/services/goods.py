from typing import List

from src.database import models
from src.repositories.goods import GoodsRepository
from src.utils.exceptions import BadRequestException


class GoodsService:

    def __init__(self, repository: GoodsRepository) -> None:
        self.repository = repository
        self.logger = repository.logger

    async def get_all_goods(self) -> List[models.OuterGoods]:
        goods = await self.repository.get_all_goods()
        return goods

    async def get_all_inner_goods(self) -> List[models.InnerGoods]:
        goods = await self.repository.get_all_inner_goods()
        return goods

    async def get_goods(self, outer_goods_id: str) -> models.OuterGoods:
        goods = await self.repository.get_goods(outer_goods_id)
        return goods

    async def edit(self, outer_goods_id: str, inner_goods_name: str) -> models.OuterGoods:
        # Получаем запись из БД
        outer_goods = await self.repository.get_goods(outer_goods_id)
        if not outer_goods:
            raise BadRequestException('Запись не найдена')

        # Обновляем данные, сохраняем в БД
        inner_goods = outer_goods.inner_goods
        await self.repository.update_object(inner_goods, {"name": inner_goods_name})

        # Формируем ответ
        inner_goods.name = inner_goods_name
        return outer_goods
