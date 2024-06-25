import uuid
from typing import Any, List

from fastapi import APIRouter, Depends

from src.depends import get_service_card_type
from src.schemas.card_type import CardTypeReadSchema, CardTypeCreateSchema, CardTypeEditSchema
from src.schemas.common import SuccessSchema
from src.services.card_type import CardTypeService
from src.utils import enums
from src.descriptions.card_type import delete_card_type_description, get_card_types_description, \
    edit_card_type_description, create_card_type_description, card_type_tag_description
from src.utils.exceptions import ForbiddenException
from src.utils.schemas import MessageSchema

router = APIRouter()
card_type_tag_metadata = {
    "name": "card_type",
    "description": card_type_tag_description,
}


@router.get(
    path="/card_type/all",
    tags=["card_type"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[CardTypeReadSchema],
    summary = 'Получение списка типов карт',
    description = get_card_types_description
)
async def get_card_types(
    service: CardTypeService = Depends(get_service_card_type)
):
    # Получить список типов карт могут пользователи с любой ролью.
    card_types = await service.get_card_types()
    return card_types


@router.post(
    path="/card_type/create",
    tags=["card_type"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = CardTypeReadSchema,
    summary = 'Создание типа карт',
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


@router.put(
    path="/card_type/{id}/edit",
    tags=["card_type"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = CardTypeReadSchema,
    summary = 'Редактирование типа карт',
    description = edit_card_type_description
)
async def edit(
    id: uuid.UUID,
    data: CardTypeEditSchema,
    service: CardTypeService = Depends(get_service_card_type)
) -> CardTypeReadSchema:
    id = str(id)
    # Проверка прав доступа. Редактировать типы карт может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    card_type = await service.edit(id, data)
    return card_type


@router.delete(
    path="/card_type/{id}/delete",
    tags=["card_type"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SuccessSchema,
    summary = 'Удаление типа карт',
    description = delete_card_type_description
)
async def delete(
    id: uuid.UUID,
    service: CardTypeService = Depends(get_service_card_type)
) -> dict[str, Any]:
    id = str(id)
    # Проверка прав доступа. Удалять может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    await service.delete(id)
    return {'success': True}
