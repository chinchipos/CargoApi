import uuid
from typing import Any, List, Optional

from fastapi import APIRouter, Depends

from src.depends import get_service_card
from src.schemas.card import CardReadSchema, CardCreateSchema, CardEditSchema
from src.schemas.common import SuccessSchema
from src.services.card import CardService
from src.utils import enums
from src.utils.descriptions.card import delete_card_description, get_cards_description, edit_card_description, \
    create_card_description, card_tag_description, get_card_description
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
    card: CardCreateSchema,
    systems: Optional[List[uuid.UUID]] = [],
    service: CardService = Depends(get_service_card)
) -> CardReadSchema:
    # Создавать карты может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    systems = [str(system) for system in systems]
    card = await service.create(card, systems)
    return card


@router.get(
    path="/card/{id}",
    tags=["card"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = CardReadSchema,
    name = 'Получение сведений о карте',
    description = get_card_description
)
async def get_card(
    id: uuid.UUID,
    service: CardService = Depends(get_service_card)
) -> CardReadSchema:
    id = str(id)
    card = await service.get_card(id)

    # Проверка прав доступа.
    # Суперадмин имеет права на все организации.
    # Менеджер ПроАВТО имеет права в отношении администрируемых им организаций.
    # Администратор компании, логист и водитель могут получать сведения только по своей организации.
    minor_roles = [enums.Role.COMPANY_ADMIN.name, enums.Role.COMPANY_LOGIST.name, enums.Role.COMPANY_DRIVER.name]
    if service.repository.user.role.name == enums.Role.CARGO_MANAGER.name:
        if not service.repository.user.is_admin_for_company(card.company_id):
            raise ForbiddenException()

    elif service.repository.user.role.name in minor_roles:
        if not service.repository.user.is_worker_of_company(card.company_id):
            raise ForbiddenException()

    card_data = card.dumps()
    card_data['systems'] = [cs.system for cs in card.card_system]
    card_read_schema = CardReadSchema(**card_data)
    return card_read_schema


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
    card: CardEditSchema,
    systems: Optional[List[uuid.UUID]] = [],
    service: CardService = Depends(get_service_card)
) -> CardReadSchema:
    id = str(id)
    # Право редактирования есть у сотрудников ПроАВТО, администратора организации и логиста.
    # У водителя нет прав.
    # Дополнительная проверка прав доступа будет выполнена на следующем этапе.
    allowed_roles = [
        enums.Role.CARGO_SUPER_ADMIN.name,
        enums.Role.CARGO_MANAGER.name,
        enums.Role.COMPANY_ADMIN.name,
        enums.Role.COMPANY_LOGIST.name
    ]
    if service.repository.user.role.name not in allowed_roles:
        raise ForbiddenException()

    systems = [str(system) for system in systems]
    card = await service.edit(id, card, systems)
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
    # Удалять может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    await service.delete(id)
    return {'success': True}
