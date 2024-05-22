from typing import List, Optional

from src.auth.manager import create_user
from src.config import BUILTIN_ADMIN_EMAIL
from src.database import models
from src.repositories.user import UserRepository
from src.schemas.user import UserCargoReadSchema, UserCreateSchema, UserEditSchema, UserReadSchema
from src.utils import enums
from src.utils.exceptions import ForbiddenException, BadRequestException
from src.utils.password_policy import test_password_strength


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
