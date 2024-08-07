import uuid
from typing import List

from fastapi import APIRouter, Depends

from src.depends import get_service_system
from src.schemas.system import SystemReadSchema, SystemEditSchema
from src.services.system import SystemService
from src.utils import enums
from src.descriptions.system import get_systems_description, edit_system_description, system_tag_description
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
    summary = 'Получение списка всех поставщиков услуг',
    description = get_systems_description
)
async def get_systems(
    service: SystemService = Depends(get_service_system)
):
    systems = await service.get_systems()
    return systems

"""
@router.post(
    path="/system/create",
    tags=["system"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SystemReadSchema,
    summary = 'Создание поставщика услуг',
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
"""


@router.put(
    path="/system/{id}/edit",
    tags=["system"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SystemReadSchema,
    summary = 'Редактирование поставщика услуг',
    description = edit_system_description
)
async def edit(
    id: uuid.UUID,
    data: SystemEditSchema,
    service: SystemService = Depends(get_service_system)
):
    id = str(id)
    # Проверка прав доступа. Редактировать системы может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    system = await service.edit(id, data)
    return system

"""
@router.delete(
    path="/system/{id}/delete",
    tags=["system"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SuccessSchema,
    summary = 'Удаление поставщика услуг',
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
"""
