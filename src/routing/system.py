import uuid
from typing import Any, List

from fastapi import APIRouter, Depends

from src.depends import get_service_system
from src.schemas.common import SuccessSchema
from src.schemas.system import SystemReadSchema, SystemCreateSchema, SystemEditSchema
from src.services.system import SystemService
from src.utils import enums
from src.utils.descriptions.system import delete_system_description, get_systems_description, edit_system_description, \
    create_system_description, system_tag_description
from src.utils.exceptions import ForbiddenException
from src.utils.schemas import MessageSchema


router = APIRouter()
system_tag_metadata = {
    "name": "system",
    "description": system_tag_description,
}


@router.get(
    path="/system/all",
    tags=["system"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[SystemReadSchema],
    name = 'Получение списка всех поставщиков услуг',
    description = get_systems_description
)
async def get_systems(
    service: SystemService = Depends(get_service_system)
):
    # Проверка прав доступа. Получить список систем может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    systems = await service.get_systems()
    return systems


@router.post(
    path="/system/create",
    tags=["system"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SystemReadSchema,
    name = 'Создание поставщика услуг',
    description = create_system_description
)
async def create(
    data: SystemCreateSchema,
    service: SystemService = Depends(get_service_system)
) -> SystemReadSchema:
    # Проверка прав доступа. Создавать системы может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    system = await service.create(data)
    return system


@router.post(
    path="/system/{id}/edit",
    tags=["system"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SystemReadSchema,
    name = 'Редактирование поставщика услуг',
    description = edit_system_description
)
async def edit(
    id: uuid.UUID,
    data: SystemEditSchema,
    service: SystemService = Depends(get_service_system)
) -> SystemReadSchema:
    id = str(id)
    # Проверка прав доступа. Редактировать системы может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    system = await service.edit(id, data)
    return system


@router.get(
    path="/system/{id}/delete",
    tags=["system"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SuccessSchema,
    name = 'Удаление поставщика услуг',
    description = delete_system_description
)
async def delete(
    id: uuid.UUID,
    service: SystemService = Depends(get_service_system)
) -> dict[str, Any]:
    id = str(id)
    # Проверка прав доступа. Удалять может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    await service.delete(id)
    return {'success': True}
