from typing import Any, List

from fastapi import APIRouter, Depends

from src.depends import get_service_card_type
from src.schemas.common import SuccessSchema, ModelIDSchema
from src.schemas.card_type import CardTypeReadSchema, CardTypeCreateSchema, CardTypeEditSchema
from src.services.card_type import CardTypeService
from src.utils import enums
from src.utils.descriptions.card_type import delete_card_type_description, get_card_types_description, \
    edit_card_type_description, create_card_type_description, card_type_tag_description
from src.utils.exceptions import ForbiddenException
from src.utils.schemas import MessageSchema


router = APIRouter()
card_type_tag_metadata = {
    "name": "card_type",
    "description": card_type_tag_description,
}


@router.post(
    path="/card_type/create",
    tags=["card_type"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = CardTypeReadSchema,
    description = create_card_type_description
)
async def create(
    data: CardTypeCreateSchema,
    service: CardTypeService = Depends(get_service_card_type)
) -> CardTypeReadSchema:
    # Проверка прав доступа. Создавать типы карт может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    card_type = await service.create(data)
    return card_type


@router.post(
    path="/card_type/edit",
    tags=["card_type"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = CardTypeReadSchema,
    description = edit_card_type_description
)
async def edit(
    data: CardTypeEditSchema,
    service: CardTypeService = Depends(get_service_card_type)
) -> CardTypeReadSchema:
    # Проверка прав доступа. Редактировать типы карт может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    card_type = await service.edit(data)
    return card_type


@router.get(
    path="/card_type/get_card_types",
    tags=["card_type"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[CardTypeReadSchema],
    description = get_card_types_description
)
async def get_card_types(
    service: CardTypeService = Depends(get_service_card_type)
):
    # Получить список типов карт могут пользователи с любой ролью.
    card_types = await service.get_card_types()
    return card_types


@router.post(
    path="/card_type/delete",
    tags=["card_type"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SuccessSchema,
    description = delete_card_type_description
)
async def delete(
    data: ModelIDSchema,
    service: CardTypeService = Depends(get_service_card_type)
) -> dict[str, Any]:
    # Проверка прав доступа. Удалять может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    await service.delete(data)
    return {'success': True}
