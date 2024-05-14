from typing import Any, List

from fastapi import APIRouter, Depends

from src.depends import get_service_tariff
from src.schemas.common import SuccessSchema, ModelIDSchema
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


@router.post(
    path="/tariff/create",
    tags=["tariff"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = TariffReadSchema,
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
    path="/tariff/edit",
    tags=["tariff"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = TariffReadSchema,
    description = edit_tariff_description
)
async def edit(
    data: TariffEditSchema,
    service: TariffService = Depends(get_service_tariff)
) -> TariffReadSchema:
    # Проверка прав доступа. Редактировать тарифы может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    tariff = await service.edit(data)
    return tariff


@router.get(
    path="/tariff/get_tariffs",
    tags=["tariff"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[TariffReadSchema],
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
    path="/tariff/delete",
    tags=["tariff"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SuccessSchema,
    description = delete_tariff_description
)
async def delete(
    data: ModelIDSchema,
    service: TariffService = Depends(get_service_tariff)
) -> dict[str, Any]:
    # Проверка прав доступа. Удалять может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    await service.delete(data)
    return {'success': True}
