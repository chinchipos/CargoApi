from sqlalchemy import select as sa_select
from sqlalchemy.orm import joinedload

from src.database import models
from src.repositories.base import BaseRepository
from src.schemas.user import UserCreateSchema


class UserRepository(BaseRepository):

    async def get_user(self, user_id: str) -> models.User:
        stmt = (
            sa_select(models.User)
            .options(joinedload(models.User.role))
            .where(models.User.id == user_id)
            .limit(1)
        )
        dataset = await self.session.scalars(stmt)
        user = dataset.first()
        return user

    async def create_user(self, user: UserCreateSchema) -> models.User:
        new_user = models.User(**user.model_dump())
        await self.save_object(new_user)
        await self.load_user_profile(new_user.id)
        return self.user
