from datetime import timedelta, datetime, timezone
from typing import List, Optional, Dict, Any

from src.auth.manager import create_user
from src.config import BUILTIN_ADMIN_EMAIL, JWT_SECRET
from src.database import models
from src.repositories.user import UserRepository
from src.schemas.role import RoleReadSchema
from src.schemas.user import UserCargoReadSchema, UserCreateSchema, UserEditSchema, UserReadSchema, \
    UserImpersonatedSchema
from src.utils import enums
from src.utils.exceptions import ForbiddenException, BadRequestException
from src.utils.password_policy import test_password_strength

import jwt


class UserService:

    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    async def create(
        self,
        user_create_schema: UserCreateSchema,
        managed_companies_ids: Optional[List[str]]
    ) -> models.User:
        # Получаем роль из БД
        role = await self.repository.get_role(user_create_schema.role_id)

        # Проверка сложности пароля
        test_password_strength(role.name, user_create_schema.password)

        # Создаем пользователя
        new_user = await create_user(user_create_schema)

        # Получаем полный профиль пользователя
        new_user = await self.repository.get_user(new_user.id)

        # Выполняем привязку к администрируемым компаниям
        await self.binding_managed_companies(
            new_user.id,
            new_user.role.name,
            current_managed_companies_ids = [],
            new_managed_companies_ids = managed_companies_ids
        )

        return new_user

    async def get_me(self) -> models.User:
        me = await self.repository.get_user(self.repository.user.id)
        return me

    async def get_user(self, user_id: str) -> models.User:
        user = await self.repository.get_user(user_id)
        if not user:
            raise BadRequestException('Пользователь не найден')
        return user

    async def get_companies_users(self) -> List[models.User]:
        users = await self.repository.get_companies_users()
        return users

    async def get_cargo_users(self) -> List[UserCargoReadSchema]:
        # Получаем пользователей из БД
        users = await self.repository.get_cargo_users()

        # Формируем ответ
        users_data = [user.dumps() for user in users]
        for user_data in users_data:
            user_data['managed_companies'] = [ac.company for ac in user_data['admin_company']]

        user_cargo_read_schemas = [UserCargoReadSchema.model_validate(user_data) for user_data in users_data]
        return user_cargo_read_schemas

    async def binding_managed_companies(
            self,
            user_id: str,
            role_name: str,
            current_managed_companies_ids: List[str],
            new_managed_companies_ids: List[str]
    ) -> None:
        if role_name == enums.Role.CARGO_MANAGER.name:
            to_unbind = [_id_ for _id_ in current_managed_companies_ids if _id_ not in new_managed_companies_ids]
            await self.repository.unbind_managed_companies(user_id, to_unbind)

            to_bind = [_id_ for _id_ in new_managed_companies_ids if _id_ not in current_managed_companies_ids]
            await self.repository.bind_managed_companies(user_id, to_bind)

        else:
            to_unbind = current_managed_companies_ids
            await self.repository.unbind_managed_companies(user_id, to_unbind)

    async def edit(
        self,
        user_id: str,
        user_edit_schema: UserEditSchema,
        managed_companies_ids: Optional[List[str]]
    ) -> UserReadSchema:
        # Право на редактирование есть только у суперадмина ПроАВТО.
        if self.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
            raise ForbiddenException()

        # Получаем пользователя из БД
        user_obj = await self.get_user(user_id)

        # У суперадмина для редактирования доступны только определенные поля:
        #  -> пароль
        if user_obj.email == BUILTIN_ADMIN_EMAIL:
            user_edit_schema = UserEditSchema(
                password=user_edit_schema.password,
                email=BUILTIN_ADMIN_EMAIL
            )

        # Обновляем данные пользователя, сохраняем в БД
        update_data = user_edit_schema.model_dump(exclude_unset=True)
        await self.repository.update_object(user_obj, update_data)

        # Отвязываем неактуальные организации, привязываем новые
        await self.binding_managed_companies(
            user_obj.id,
            user_obj.role.name,
            current_managed_companies_ids = [ac.company_id for ac in user_obj.admin_company],
            new_managed_companies_ids = managed_companies_ids
        )

        # Формируем ответ
        user = await self.repository.get_user(user_id)
        user_read_schema = UserReadSchema.model_validate(user)
        return user_read_schema

    async def delete(self, user_id: str) -> None:
        # Получаем пользователя из БД
        user_obj = await self.get_user(user_id)

        # Нельзя удалять встроенного суперадмина
        if user_obj.email == BUILTIN_ADMIN_EMAIL:
            raise BadRequestException("Невозможно удалить встроенного администратора")

        await self.repository.delete_object(models.User, user_id)

    def create_access_token(self, data: Dict[str, Any], expires_delta: timedelta | None = None) -> str:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm="HS256")
        return encoded_jwt

    async def impersonate(self, user_id: str) -> UserImpersonatedSchema:
        # Получаем пользователя из БД
        user = await self.repository.get_user(user_id)

        # Проверка прав доступа.
        # Суперадмин ПроАВТО имеет полные права в отношении пользователей с нижестоящей ролью.
        # Менеджер ПроАВТО имеет права в отношении пользователей администрируемых организаций с нижестоящей ролью.
        # Остальные роли не имеют прав.
        if self.repository.user.role.name == enums.Role.CARGO_SUPER_ADMIN.name:
            if user.role.name == enums.Role.CARGO_SUPER_ADMIN.name:
                raise ForbiddenException()

        elif self.repository.user.role.name == enums.Role.CARGO_MANAGER.name:
            if not user.company_id or not self.repository.user.is_admin_for_company(user.company_id) or \
                    user.role.name in [enums.Role.CARGO_SUPER_ADMIN.name, enums.Role.CARGO_MANAGER.name]:
                raise ForbiddenException()

        else:
            raise ForbiddenException()

        # Создаем токен
        access_token_expires = timedelta(minutes=30)
        access_token = self.create_access_token(
            data={"sub": user.id, "aud": ["fastapi-users:auth"]},
            expires_delta=access_token_expires
        )

        role_schema = RoleReadSchema(**user.role.dumps())
        impersonated_user_schema = UserImpersonatedSchema(
            id=user.id,
            access_token=access_token,
            token_type="bearer",
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            is_active=user.is_active,
            role=role_schema
        )
        return impersonated_user_schema
