import uuid
from typing import List, Optional, Any

from fastapi import APIRouter, Depends

from src.database import models
from src.depends import get_service_user
from src.schemas.common import SuccessSchema
from src.schemas.user import UserReadSchema, UserCompanyReadSchema, UserCargoReadSchema, UserCreateSchema, \
    UserEditSchema, UserImpersonatedSchema
from src.services.user import UserService
from src.utils import enums
from src.utils.descriptions.user import user_tag_description, get_me_description, get_companies_users_description, \
    get_cargo_users_description, create_user_description, edit_user_description, delete_user_description
from src.utils.exceptions import ForbiddenException
from src.utils.schemas import MessageSchema


router = APIRouter()
user_tag_metadata = {
    "name": "user",
    "description": user_tag_description,
}


@router.post(
    path="/user/create",
    tags=["user"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = UserReadSchema,
    name = 'Создание поставщика услуг',
    description = create_user_description
)
async def create(
    user: UserCreateSchema,
    managed_companies: Optional[List[uuid.UUID]] = [],
    service: UserService = Depends(get_service_user)
) -> models.User:
    # Создавать пользователей может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    managed_companies = [str(company) for company in managed_companies]
    new_user = await service.create(user, managed_companies)
    return new_user


@router.get(
    path="/user/me",
    tags=["user"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = UserReadSchema,
    name = 'Получение себственного профиля',
    description = get_me_description
)
async def get_me(
    user_service: UserService = Depends(get_service_user)
) -> models.User:
    user = await user_service.get_me()
    return user


@router.get(
    path="/user/company/all",
    tags=["user"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[UserCompanyReadSchema],
    name = 'Получение списка пользователей (сотрудники организаций)',
    description = get_companies_users_description
)
async def get_companies_users(
    service: UserService = Depends(get_service_user)
) -> List[models.User]:
    # Проверка прав доступа.
    # Суперадмин ПроАВТО не имеет ограничений.
    # Менеджер ПроАВТО имеет права в рамках своих организаций.
    # Остальные роли не имеют прав.
    # Состав списка пользователей зависит от роли - проверка будет выполнена при формировании списка.
    allowed_roles = [enums.Role.CARGO_SUPER_ADMIN.name, enums.Role.CARGO_MANAGER.name, enums.Role.COMPANY_ADMIN.name]
    if service.repository.user.role.name not in allowed_roles:
        raise ForbiddenException()

    users = await service.get_companies_users()
    return users


@router.get(
    path="/user/cargo/all",
    tags=["user"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[UserCargoReadSchema],
    name = 'Получение списка пользователей (сотрудники ПроАВТО)',
    description = get_cargo_users_description
)
async def get_cargo_users(
    service: UserService = Depends(get_service_user)
) -> List[UserCargoReadSchema]:
    # Доступ разрешен только суперадмину ПроАВТО
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    users = await service.get_cargo_users()
    return users


@router.post(
    path="/user/{id}/edit",
    tags=["user"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = UserEditSchema,
    name = 'Редактирование пользователя',
    description = edit_user_description
)
async def edit(
    id: uuid.UUID,
    user: UserEditSchema,
    managed_companies: Optional[List[uuid.UUID]] = [],
    service: UserService = Depends(get_service_user)
) -> UserReadSchema:
    id = str(id)
    # Проверка прав доступа. Редактировать записи может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    managed_companies = [str(company) for company in managed_companies]
    user = await service.edit(id, user, managed_companies)
    return user


@router.get(
    path="/user/{id}/delete",
    tags=["user"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SuccessSchema,
    name = 'Удаление пользователя',
    description = delete_user_description
)
async def delete(
    id: uuid.UUID,
    service: UserService = Depends(get_service_user)
) -> dict[str, Any]:
    id = str(id)
    # Удалять может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    await service.delete(id)
    return {'success': True}


@router.get(
    path="/user/{id}/impersonate",
    tags=["user"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = UserImpersonatedSchema,
    name = 'Вход под пользователем',
    description = edit_user_description
)
async def edit(
    id: uuid.UUID,
    service: UserService = Depends(get_service_user)
) -> UserImpersonatedSchema:
    id = str(id)
    impersonated_user = await service.impersonate(id)
    return impersonated_user
