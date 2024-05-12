from src.database import models
from src.repositories.base import BaseRepository
from src.schemas.db import DBSyncSchema
from src.utils.exceptions import DBException
from src.utils import enums

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import select as sa_select


class DBRepository(BaseRepository):

    async def init_roles(self) -> None:
        dataset = [
            {
                'name': role.name,
                'title': role.value['title'],
                'description': role.value['description']
            } for role in enums.Role
        ]
        stmt = pg_insert(models.Role).on_conflict_do_nothing()
        try:
            async with self.session.begin():
                await self.session.execute(stmt, dataset)
                await self.session.commit()
        except Exception:
            raise DBException()

    async def init_card_types(self) -> None:
        dataset = [
            {'name': 'Пластиковая карта'},
            {'name': 'Виртуальная карта'}
        ]
        stmt = pg_insert(models.CardType).on_conflict_do_nothing()
        try:
            await self.session.execute(stmt, dataset)
            await self.session.commit()
        except Exception as e:
            raise DBException()

    async def get_cargo_superadmin_role(self) -> models.Role:
        try:
            stmt = sa_select(models.Role).where(models.Role.name == enums.Role.CARGO_SUPER_ADMIN.name).limit(1)
            dataset = await self.session.scalars(stmt)
            role = dataset.first()
            return role

        except Exception as e:
            raise DBException()

    async def sync(self, data: DBSyncSchema) -> bool:
        return True
