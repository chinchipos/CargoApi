from typing import Any, List

from fastapi import APIRouter, Depends

from src.depends import get_service_card
from src.schemas.common import SuccessSchema, ModelIDSchema
from src.schemas.card import CardReadSchema, CardCreateSchema, CardEditSchema
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


@router.post(
    path="/card/create",
    tags=["card"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = CardReadSchema,
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
    path="/card/edit",
    tags=["card"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = CardReadSchema,
    description = edit_card_description
)
async def edit(
    data: CardEditSchema,
    service: CardService = Depends(get_service_card)
) -> CardReadSchema:
    # Проверка прав доступа будет выполнена на следующем этапе
    card = await service.edit(data)
    return card


@router.get(
    path="/card/get_cards",
    tags=["card"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[CardReadSchema],
    description = get_cards_description
)
async def get_cards(
    service: CardService = Depends(get_service_card)
):
    # Проверка прав доступа. Получить список карт могут все пользователи.
    # Состав списка определяется ролью пользователя. Эта проверка будет выполнена при формировании списка.
    cards = await service.get_cards()
    return cards


@router.post(
    path="/card/delete",
    tags=["card"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SuccessSchema,
    description = delete_card_description
)
async def delete(
    data: ModelIDSchema,
    service: CardService = Depends(get_service_card)
) -> dict[str, Any]:
    # Проверка прав доступа. Удалять может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    await service.delete(data)
    return {'success': True}
