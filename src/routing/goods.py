import uuid
from typing import List

from fastapi import APIRouter, Depends

from src.database.model import models
from src.depends import get_service_goods
from src.schemas.goods import OuterGoodsReadSchema, InnerGoodsReadSchema, InnerGoodsEditSchema
from src.services.goods import GoodsService
from src.utils import enums
from src.descriptions.goods import goods_tag_description, get_all_goods_description, get_goods_description, \
    edit_goods_description, get_all_inner_goods_description
from src.utils.exceptions import ForbiddenException
from src.utils.schemas import MessageSchema

router = APIRouter()
goods_tag_metadata = {
    "name": "goods",
    "description": goods_tag_description,
}


@router.get(
    path="/goods/outer/all",
    tags=["goods"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[OuterGoodsReadSchema],
    summary = 'Получение списка товаров/услуг',
    description = get_all_goods_description
)
async def get_all_outer_goods(
    service: GoodsService = Depends(get_service_goods)
) -> List[models.OuterGoods]:
    # Нет ограничений доступа.
    goods = await service.get_all_outer_goods()
    return goods


@router.get(
    path="/goods/inner/all",
    tags=["goods"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[InnerGoodsReadSchema],
    summary = 'Получение списка товаров/услуг (с нашим наименованием)',
    description = get_all_inner_goods_description
)
async def get_all_inner_goods(
    service: GoodsService = Depends(get_service_goods)
) -> List[models.InnerGoods]:
    # Нет ограничений доступа.
    goods = await service.get_all_inner_goods()
    return goods


@router.get(
    path="/goods/outer/{id}",
    tags=["goods"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = OuterGoodsReadSchema,
    summary = 'Получение информации о товаре/услуге',
    description = get_goods_description
)
async def get_single_goods(
    id: uuid.UUID,
    service: GoodsService = Depends(get_service_goods)
) -> models.OuterGoods:
    id = str(id)
    # Доступ не ограничивается
    goods = await service.get_single_goods(id)
    return goods


@router.put(
    path="/goods/outer/{id}/edit",
    tags=["goods"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = OuterGoodsReadSchema,
    summary = 'Редактирование товара/услуги',
    description = edit_goods_description
)
async def edit(
    id: uuid.UUID,
    data: InnerGoodsEditSchema,
    service: GoodsService = Depends(get_service_goods)
):
    id = str(id)
    # Редактировать могут только сотрудники ПроАВТО.
    if service.repository.user.role.name not in [enums.Role.CARGO_SUPER_ADMIN.name, enums.Role.CARGO_MANAGER.name]:
        raise ForbiddenException()

    goods = await service.edit(id, data)
    return goods
