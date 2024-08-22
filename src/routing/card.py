import uuid
from typing import Any, List, Dict

from fastapi import APIRouter, Depends

from src.depends import get_service_card
from src.descriptions.card import delete_card_description, get_cards_description, edit_card_description, \
    create_card_description, card_tag_description, get_card_description, bulk_bind_description, \
    bulk_unbind_systems_description, bulk_unbind_company_description, bulk_block_description, \
    bulk_activate_description, change_card_state_description
from src.schemas.card import CardReadSchema, CardCreateSchema, CardEditSchema, BulkBindSchema, BulkUnbindSchema
from src.schemas.card_limit import CardLimitParamsSchema, CardLimitReadSchema, CardLimitCreateSchema
from src.schemas.common import SuccessSchema
from src.services.card import CardService
from src.utils import enums
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
    summary = 'Получение списка всех карт',
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
    summary = 'Создание карты',
    description = create_card_description
)
async def create(
    card: CardCreateSchema,
    systems: List[uuid.UUID] | None = None,
    service: CardService = Depends(get_service_card)
) -> CardReadSchema:
    if systems is None:
        systems = []
    # Создавать карты может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    systems = [str(system) for system in systems]
    card = await service.create(card, systems)
    return card


@router.get(
    path="/card/get-limit-params",
    tags=["card"],
    responses={400: {'model': MessageSchema, "description": "Bad request"}},
    response_model=CardLimitParamsSchema,
    summary='Получение сведений о базовых параметрах лимитов',
    description='Получение сведений о базовых параметрах лимитов'
)
async def get_limit_params(
        service: CardService = Depends(get_service_card)
):
    limit_params = await service.get_limit_params()
    return limit_params


@router.put(
    path="/card/bulk/bind",
    tags=["card"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SuccessSchema,
    summary = 'Групповая привязка карт к организации и/или системам',
    description = bulk_bind_description
)
async def bulk_bind(
    data: BulkBindSchema,
    service: CardService = Depends(get_service_card)
) -> Dict[str, Any]:
    await service.bulk_bind(data.card_numbers, data.company_id, data.system_ids)
    return {'success': True}


@router.put(
    path="/card/bulk/unbind/company",
    tags=["card"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SuccessSchema,
    summary = 'Групповое открепление карт от текущей организации',
    description = bulk_unbind_company_description
)
async def bulk_unbind_company(
    data: BulkUnbindSchema,
    service: CardService = Depends(get_service_card)
) -> Dict[str, Any]:
    await service.bulk_unbind_company(data.card_numbers)
    return {'success': True}


@router.put(
    path="/card/bulk/unbind/systems",
    tags=["card"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SuccessSchema,
    summary = 'Групповое открепление карт от всех систем',
    description = bulk_unbind_systems_description
)
async def bulk_unbind_systems(
    data: BulkUnbindSchema,
    service: CardService = Depends(get_service_card)
) -> Dict[str, Any]:
    await service.bulk_unbind_systems(data.card_numbers)
    return {'success': True}


@router.put(
    path="/card/bulk/activate",
    tags=["card"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SuccessSchema,
    summary = 'Групповая разблокировка карт',
    description = bulk_activate_description
)
async def bulk_activate(
    data: BulkUnbindSchema,
    service: CardService = Depends(get_service_card)
) -> Dict[str, Any]:
    await service.bulk_activate(data.card_numbers)
    return {'success': True}


@router.put(
    path="/card/bulk/block",
    tags=["card"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SuccessSchema,
    summary = 'Групповая блокировка карт',
    description = bulk_block_description
)
async def bulk_block(
    data: BulkUnbindSchema,
    service: CardService = Depends(get_service_card)
) -> Dict[str, Any]:
    await service.bulk_block(data.card_numbers)
    return {'success': True}


@router.get(
    path="/card/{id}",
    tags=["card"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = CardReadSchema,
    summary = 'Получение сведений о карте',
    description = get_card_description
)
async def get_card(
    id: uuid.UUID,
    service: CardService = Depends(get_service_card)
):
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

    return card


@router.put(
    path="/card/{id}/edit",
    tags=["card"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = CardReadSchema,
    summary = 'Редактирование карты',
    description = edit_card_description
)
async def edit(
    id: uuid.UUID,
    card: CardEditSchema,
    systems: List[uuid.UUID] | None = None,
    service: CardService = Depends(get_service_card)
):
    id = str(id)
    if systems is None:
        systems = []
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


@router.delete(
    path="/card/{id}/delete",
    tags=["card"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SuccessSchema,
    summary = 'Удаление карты',
    description = delete_card_description
)
async def delete(
    id: uuid.UUID,
    service: CardService = Depends(get_service_card)
):
    id = str(id)
    # Удалять может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    await service.delete(id)
    return {'success': True}


@router.get(
    path="/card/{id}/set-state",
    tags=["card"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SuccessSchema,
    summary = 'Установка состояния карты: активна / заблокирована',
    description = change_card_state_description
)
async def set_state(
    id: uuid.UUID,
    activate: bool,
    service: CardService = Depends(get_service_card)
):
    id = str(id)
    # Изменять состояние карты могут только суперадмин, менеджер ПроАВТО, администратор и логист организации.
    roles = [enums.Role.CARGO_SUPER_ADMIN.name, enums.Role.CARGO_MANAGER.name,
             enums.Role.COMPANY_ADMIN, enums.Role.COMPANY_LOGIST]
    if service.repository.user.role.name not in roles:
        raise ForbiddenException()

    await service.set_state(id, activate)
    return {'success': True}


@router.post(
    path="/card/{id}/set-limits",
    tags=["card"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[CardLimitReadSchema],
    summary = 'Установка новых лимитов взамен существующих',
    description = 'Установка новых лимитов взамен существующих'
)
async def set_limits(
    id: uuid.UUID,
    limits: List[CardLimitCreateSchema],
    service: CardService = Depends(get_service_card)
):
    id = str(id)
    card = await service.get_card(id)

    # Проверка прав доступа.
    # Суперадмин имеет права на все карты.
    # Менеджер ПроАВТО имеет права на карты в отношении администрируемых им организаций.
    # Администратор компанииимеет права только по своей организации.
    # У остальных ролей нет прав
    if service.repository.user.role.name == enums.Role.CARGO_SUPER_ADMIN.name:
        pass
    
    elif service.repository.user.role.name == enums.Role.CARGO_MANAGER.name:
        if not service.repository.user.is_admin_for_company(card.company_id):
            raise ForbiddenException()

    elif service.repository.user.role.name == enums.Role.COMPANY_ADMIN.name:
        if not service.repository.user.is_worker_of_company(card.company_id):
            raise ForbiddenException()

    new_limits = await service.set_limits(card=card, company=card.company, limits=limits)
    return new_limits
