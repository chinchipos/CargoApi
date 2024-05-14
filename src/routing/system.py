from typing import Any, List

from fastapi import APIRouter, Depends

from src.database import models
from src.depends import get_service_system
from src.routing.descriptions import get_systems_descr, delete_system_descr, edit_system_descr, create_system_descr
from src.schemas.common import SuccessSchema
from src.schemas.system import SystemReadSchema, SystemCreateSchema, SystemEditSchema, SystemDeleteSchema
from src.services.system import SystemService
from src.utils.schemas import MessageSchema


router = APIRouter()
system_tag_metadata = {
    "name": "system",
    "description": "Операции с системами поставщиков услуг.",
}


@router.post(
    path="/system/create",
    tags=["system"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SystemReadSchema,
    description = create_system_descr
)
async def create(
    data: SystemCreateSchema,
    service: SystemService = Depends(get_service_system)
) -> SystemReadSchema:
    system = await service.create(data)
    return system


@router.post(
    path="/system/edit",
    tags=["system"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SystemReadSchema,
    description = edit_system_descr
)
async def edit(
    data: SystemEditSchema,
    service: SystemService = Depends(get_service_system)
) -> SystemReadSchema:
    system = await service.edit(data)
    return system


@router.get(
    path="/system/get_systems",
    tags=["system"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[SystemReadSchema],
    description = get_systems_descr
)
async def get_systems(
    service: SystemService = Depends(get_service_system)
):
    systems = await service.get_systems()
    print('YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY')
    return systems


@router.post(
    path="/system/delete",
    tags=["system"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SuccessSchema,
    description = delete_system_descr
)
async def delete(
    data: SystemDeleteSchema,
    service: SystemService = Depends(get_service_system)
) -> dict[str, Any]:
    await service.delete(data)
    return {'success': True}
