from typing import List

from fastapi import APIRouter, Depends

from src.database import models
from src.depends import get_service_user
from src.schemas.user import UserReadSchema, UserCompanyReadSchema, UserCargoReadSchema, UserCreateSchema
from src.services.user import UserService
from src.utils import enums
from src.utils.descriptions.user import user_tag_description, get_me_description, get_companies_users_description, \
    get_cargo_users_description, create_user_description
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
    data: UserCreateSchema,
    service: UserService = Depends(get_service_user)
) -> models.User:
    # Создавать пользователей может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    new_user = await service.create(data)
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
    if service.repository.user.role.name not in [enums.Role.CARGO_SUPER_ADMIN.name, enums.Role.CARGO_MANAGER.name]:
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
