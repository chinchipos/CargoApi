from typing import List

from src.auth.manager import create_user
from src.database import models
from src.repositories.user import UserRepository

from sqlalchemy import select as sa_select

from src.schemas.user import UserCargoReadSchema, UserCreateSchema


class UserService:

    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    async def create(self, user_create_schema: UserCreateSchema) -> models.User:
        new_user = await create_user(user_create_schema)
        return new_user

    async def get_me(self) -> models.User:
        me = await self.repository.get_user(self.repository.user.id)
        return me

    async def get_companies_users(self) -> List[models.User]:
        users = await self.repository.get_companies_users()
        return users

    async def get_cargo_users(self) -> List[UserCargoReadSchema]:
        # Получаем пользователей из БД
        users = await self.repository.get_cargo_users()

        # Формируем ответ
        users_data = [user.dumps() for user in users]
        for user_data in users_data:
            user_data['companies'] = [ac.company for ac in user_data['admin_company']]

        user_cargo_read_schemas = [UserCargoReadSchema.model_validate(user_data) for user_data in users_data]
        return user_cargo_read_schemas
