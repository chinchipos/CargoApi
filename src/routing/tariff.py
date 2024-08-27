import uuid
from typing import List

from fastapi import APIRouter, Depends

from src.depends import get_service_tariff
from src.descriptions.tariff import delete_tariff_description, get_tariffs_description, edit_tariff_description, \
    create_tariff_description, tariff_tag_description
from src.schemas.common import SuccessSchema
from src.schemas.tariff import TariffReadSchema, TariffEditSchema, TariffPoliciesReadSchema, \
    TariffNewCreateSchema
from src.services.tariff import TariffService
from src.utils import enums
from src.utils.exceptions import ForbiddenException
from src.utils.schemas import MessageSchema

router = APIRouter()
tariff_tag_metadata = {
    "name": "tariff",
    "description": tariff_tag_description,
}


@router.get(
    path="/tariff/all",
    tags=["tariff"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[TariffReadSchema],
    summary = 'Получение списка тарифов',
    description = get_tariffs_description
)
async def get_tariffs(
    service: TariffService = Depends(get_service_tariff)
):
    # Проверка прав доступа. Получить список систем могут только сотрудники ПроАвто и администратор организации.
    major_roles = [enums.Role.CARGO_SUPER_ADMIN.name, enums.Role.CARGO_MANAGER.name, enums.Role.COMPANY_ADMIN.name]
    if service.repository.user.role.name not in major_roles:
        raise ForbiddenException()

    tariffs = await service.get_tariffs()
    return tariffs


@router.get(
    path="/tariff/new/all",
    tags=["tariff"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = TariffPoliciesReadSchema,
    summary = 'Получение списка тарифов',
    description = get_tariffs_description
)
async def get_tariffs_new(
    with_dictionaries: bool = False,
    policy_id: str = None,
    system_id: str = None,
    azs_id: str = None,
    azs_own_type_id: str = None,
    region_id: str = None,
    category_id: str = None,
    group_id: str = None,
    service: TariffService = Depends(get_service_tariff)
):
    # Проверка прав доступа. Получить список тарифов могут только сотрудники ПроАвто
    major_roles = [enums.Role.CARGO_SUPER_ADMIN.name, enums.Role.CARGO_MANAGER.name]
    if service.repository.user.role.name not in major_roles:
        raise ForbiddenException()

    filters = {
        "policy_id": policy_id,
        "system_id": system_id,
        "azs_id": azs_id,
        "azs_own_type_id": azs_own_type_id,
        "region_id": region_id,
        "category_id": category_id,
        "group_id": group_id,
    }

    tariff_polices = await service.get_tariff_polices(with_dictionaries=with_dictionaries, filters=filters)
    return tariff_polices


@router.post(
    path="/tariff/save",
    tags=["tariff"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SuccessSchema,
    summary = 'Создание тарифа',
    description = create_tariff_description
)
async def save(
    data: TariffNewCreateSchema,
    service: TariffService = Depends(get_service_tariff)
):
    # Проверка прав доступа. Создавать системы может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    await service.save(data)
    return {'success': True}


"""
@router.put(
    path="/tariff/{id}/edit",
    tags=["tariff"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = TariffReadSchema,
    summary = 'Редактирование тарифа',
    description = edit_tariff_description
)
async def edit(
    id: uuid.UUID,
    data: TariffEditSchema,
    service: TariffService = Depends(get_service_tariff)
):
    id = str(id)
    # Проверка прав доступа. Редактировать тарифы может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    tariff = await service.edit(id, data)
    return tariff
"""


@router.delete(
    path="/tariff/{id}/delete",
    tags=["tariff"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SuccessSchema,
    summary = 'Удаление тарифа',
    description = delete_tariff_description
)
async def delete(
    id: uuid.UUID,
    service: TariffService = Depends(get_service_tariff)
):
    id = str(id)
    # Проверка прав доступа. Удалять может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    await service.delete(id)
    return {'success': True}
