import uuid
from typing import List

from fastapi import APIRouter, Depends

from src.database.models.goods import OuterGoodsOrm
from src.depends import get_service_goods
from src.descriptions.goods import goods_tag_description, get_all_goods_description, get_goods_description, \
    edit_goods_description
from src.schemas.goods import OuterGoodsItemReadSchema, InnerGoodsEditSchema, OuterGoodsReadSchema
from src.services.goods import GoodsService
from src.utils import enums
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
    response_model = OuterGoodsReadSchema,
    summary = 'Получение списка товаров/услуг',
    description = get_all_goods_description
)
async def get_all_outer_goods(
    with_dictionaries: bool = False,
    service: GoodsService = Depends(get_service_goods)
):
    # Нет ограничений доступа.
    goods = await service.get_all_outer_goods(with_dictionaries=with_dictionaries)

    return goods


"""
@router.get(
    path="/goods/inner/names",
    tags=["goods"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = InnerGoodsNameSchema,
    summary = 'Получение списка наименований продуктов в системе ННК',
    description = 'Получение списка наименований продуктов в системе ННК'
)
async def get_inner_goods_names(
    service: GoodsService = Depends(get_service_goods)
):
    # Нет ограничений доступа.
    names = await service.get_inner_goods_names()
    return {"inner_googs_names": names}


@router.get(
    path="/goods/inner/groups",
    tags=["goods"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[InnerGoodsGroupReadSchema],
    summary = 'Получение списка групп продуктов в системе ННК',
    description = 'Получение списка групп продуктов в системе ННК'
)
async def get_inner_groups(
    service: GoodsService = Depends(get_service_goods)
):
    # Нет ограничений доступа.
    inner_groups = await service.get_inner_groups()
    return inner_groups
"""

"""
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
) -> List[InnerGoodsOrm]:
    # Нет ограничений доступа.
    goods = await service.get_all_inner_goods()
    return goods
"""

"""
@router.get(
    path="/goods/outer/{id}",
    tags=["goods"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = OuterGoodsItemReadSchema,
    summary = 'Получение информации о товаре/услуге',
    description = get_goods_description
)
async def get_single_goods(
    id: uuid.UUID,
    service: GoodsService = Depends(get_service_goods)
) -> OuterGoodsOrm:
    id = str(id)
    # Доступ не ограничивается
    goods = await service.get_single_goods(id)
    return goods
"""


@router.put(
    path="/goods/outer/{id}/edit",
    tags=["goods"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = OuterGoodsItemReadSchema,
    summary = 'Редактирование товара/услуги',
    description = edit_goods_description
)
async def edit(
    id: uuid.UUID,
    data: InnerGoodsEditSchema,
    service: GoodsService = Depends(get_service_goods)
):
    outer_goods_id = str(id)
    # Редактировать могут только сотрудники ПроАВТО.
    if service.repository.user.role.name not in [enums.Role.CARGO_SUPER_ADMIN.name, enums.Role.CARGO_MANAGER.name]:
        raise ForbiddenException()

    goods = await service.edit(outer_goods_id, data)
    return goods
