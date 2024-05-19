import uuid
from typing import Any, List

from fastapi import APIRouter, Depends

from src.depends import get_service_tariff
from src.schemas.common import SuccessSchema
from src.schemas.tariff import TariffReadSchema, TariffCreateSchema, TariffEditSchema
from src.services.tariff import TariffService
from src.utils import enums
from src.utils.descriptions.tariff import delete_tariff_description, get_tariffs_description, edit_tariff_description, \
    create_tariff_description, tariff_tag_description
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
    name = 'Получение списка тарифов',
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


@router.post(
    path="/tariff/create",
    tags=["tariff"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = TariffReadSchema,
    name = 'Создание тарифа',
    description = create_tariff_description
)
async def create(
    data: TariffCreateSchema,
    service: TariffService = Depends(get_service_tariff)
) -> TariffReadSchema:
    # Проверка прав доступа. Создавать системы может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    tariff = await service.create(data)
    return tariff


@router.post(
    path="/tariff/{tariff_id}/edit",
    tags=["tariff"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = TariffReadSchema,
    name = 'Редактирование тарифа',
    description = edit_tariff_description
)
async def edit(
    tariff_id: uuid.UUID,
    data: TariffEditSchema,
    service: TariffService = Depends(get_service_tariff)
) -> TariffReadSchema:
    _id_ = str(tariff_id)
    # Проверка прав доступа. Редактировать тарифы может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    tariff = await service.edit(_id_, data)
    return tariff


@router.post(
    path="/tariff/{tariff_id}/delete",
    tags=["tariff"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SuccessSchema,
    name = 'Удаление тарифа',
    description = delete_tariff_description
)
async def delete(
    tariff_id: uuid.UUID,
    service: TariffService = Depends(get_service_tariff)
) -> dict[str, Any]:
    _id_ = str(tariff_id)
    # Проверка прав доступа. Удалять может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    await service.delete(_id_)
    return {'success': True}
