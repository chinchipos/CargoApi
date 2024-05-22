import uuid
from typing import Any, List

from fastapi import APIRouter, Depends

from src.depends import get_service_card
from src.schemas.card import CardReadSchema, CardCreateSchema, CardEditSchema
from src.schemas.common import SuccessSchema
from src.services.card import CardService
from src.utils import enums
from src.utils.descriptions.card import delete_card_description, get_cards_description, edit_card_description, \
    create_card_description, card_tag_description
from src.utils.exceptions import ForbiddenException
from src.utils.schemas import MessageSchema

router = APIRouter()
card_tag_metadata = {
    "name": "card",
    "description": card_tag_description,
}


@router.get(
    path="/card/all",
    tags=["card"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[CardReadSchema],
    name = 'Получение списка всех карт',
    description = get_cards_description
)
async def get_cards(
    service: CardService = Depends(get_service_card)
):
    # Получить список карт могут все пользователи.
    # Состав списка определяется ролью пользователя. Эта проверка будет выполнена при формировании списка.
    cards = await service.get_cards()
    return cards


@router.post(
    path="/card/create",
    tags=["card"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = CardReadSchema,
    name = 'Создание карты',
    description = create_card_description
)
async def create(
    data: CardCreateSchema,
    service: CardService = Depends(get_service_card)
) -> CardReadSchema:
    # Проверка прав доступа. Создавать карты может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    card = await service.create(data)
    return card


@router.post(
    path="/card/{id}/edit",
    tags=["card"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = CardReadSchema,
    name = 'Редактирование карты',
    description = edit_card_description
)
async def edit(
    id: uuid.UUID,
    data: CardEditSchema,
    service: CardService = Depends(get_service_card)
) -> CardReadSchema:
    id = str(id)
    # Проверка прав доступа будет выполнена на следующем этапе
    card = await service.edit(id, data)
    return card


@router.post(
    path="/card/{id}/delete",
    tags=["card"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SuccessSchema,
    name = 'Удаление карты',
    description = delete_card_description
)
async def delete(
    id: uuid.UUID,
    service: CardService = Depends(get_service_card)
) -> dict[str, Any]:
    id = str(id)
    # Проверка прав доступа. Удалять может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    await service.delete(id)
    return {'success': True}
