import sqlalchemy as sa
from sqlalchemy.orm import joinedload

from src.database import models
from src.database.db import SessionLocal
import asyncio

from src.utils.log import logger


class BaseRepository:

    def __init__(self, session: SessionLocal, user_id: str | None = None):
        self.session = session
        self.user = None
        self.logger = logger
        if user_id:
            asyncio.run(self.load_user_profile(user_id))

    async def load_user_profile(self, user_id: str) -> None:
        stmt = (
            sa.select(models.User)
            .options(
                joinedload(models.User.role).joinedload(models.Role.role_permition).joinedload(
                    models.RolePermition.permition)
            )
            .where(models.User.id == user_id)
            .limit(1)
        )
        dataset = await self.session.scalars(stmt)
        self.user = dataset.first()

    async def delete_all(self, _model_) -> None:
        stmt = sa.delete(_model_)
        async with self.session.begin():
            await self.session.execute(stmt)
            await self.session.commit()
