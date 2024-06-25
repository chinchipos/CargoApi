from typing import List

from fastapi import APIRouter, Depends

from src.depends import get_service_role
from src.schemas.role import RoleReadSchema
from src.services.role import RoleService
from src.descriptions.role import get_roles_description, role_tag_description, get_companies_roles_description, \
    get_cargo_roles_description
from src.utils.schemas import MessageSchema

router = APIRouter()
role_tag_metadata = {
    "name": "role",
    "description": role_tag_description,
}


@router.get(
    path="/role/all",
    tags=["role"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[RoleReadSchema],
    summary = 'Получение списка всех ролей',
    description = get_roles_description
)
async def get_roles(
    service: RoleService = Depends(get_service_role)
):
    # Получить список могут все
    roles = await service.get_roles()
    return roles


@router.get(
    path="/role/company/all",
    tags=["role"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[RoleReadSchema],
    summary = 'Получение списка ролей сотрудников организаций',
    description = get_companies_roles_description
)
async def get_companies_roles(
    service: RoleService = Depends(get_service_role)
):
    # Получить список могут все
    roles = await service.get_companies_roles()
    return roles


@router.get(
    path="/role/cargo/all",
    tags=["role"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[RoleReadSchema],
    summary = 'Получение списка ролей сотрудников ПроАВТО',
    description = get_cargo_roles_description
)
async def get_cargo_roles(
    service: RoleService = Depends(get_service_role)
):
    # Получить список могут все
    roles = await service.get_cargo_roles()
    return roles
