from typing import Dict, Any

import sqlalchemy as sa
from sqlalchemy.orm import joinedload
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from src.database import models
from src.database.db import get_session
#from src.database.db import SessionLocal
import asyncio

from src.utils.exceptions import DBException, DBDuplicateException
from src.utils.log import logger

import traceback


class BaseRepository:

    def __init__(self, session: get_session, user_id: str | None = None):
        self.session = session
        self.user = None
        self.logger = logger
        if user_id:
            asyncio.run(self.load_user_profile(user_id))

    async def load_user_profile(self, user_id: str) -> None:
        try:
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

        except Exception:
            self.logger.error(traceback.format_exc())
            raise DBException()

    async def select_helper(self, stmt, scalars=True) -> Any:
        try:
            if scalars:
                result = await self.session.scalars(
                    stmt,
                    execution_options={"populate_existing": True}
                )
                result = result.unique()
            else:
                result = await self.session.execute(stmt)

            await self.session.commit()
            return result

        except Exception:
            self.logger.error(traceback.format_exc())
            raise DBException()

    async def select_all(self, stmt, scalars=True) -> Any:
        dataset = await self.select_helper(stmt, scalars)
        return dataset.all()

    async def select_first(self, stmt, scalars=True) -> Any:
        dataset = await self.select_helper(stmt, scalars)
        return dataset.first()

    async def select_single_field(self, stmt) -> Any:
        dataset = await self.select_helper(stmt, scalars=False)
        row = dataset.first()
        return row[0] if row else None

    async def delete_one(self, _model_, _id_: str):
        try:
            stmt = sa.delete(_model_).where(_model_.id == _id_)
            await self.session.execute(stmt)
            await self.session.commit()

        except Exception:
            self.logger.error(traceback.format_exc())
            raise DBException()

    async def delete_all(self, _model_) -> None:
        try:
            stmt = sa.delete(_model_)
            async with self.session.begin():
                await self.session.execute(stmt)
                await self.session.commit()

        except Exception:
            self.logger.error(traceback.format_exc())
            raise DBException()

    async def insert_or_update(self, _model_, index_field, **set_fields) -> Any:
        try:
            stmt = pg_insert(_model_).values(set_fields)
            index_elements = [index_field]
            values_set = {field: getattr(stmt.excluded, field) for field in set_fields}
            stmt = stmt.on_conflict_do_update(index_elements=index_elements, set_=values_set)
            async with self.session.begin():
                result = await self.session.scalars(
                    stmt.returning(_model_),
                    execution_options={"populate_existing": True}
                )
                await self.session.commit()
                return result.first()

        except Exception:
            self.logger.error(traceback.format_exc())
            raise DBException()

    async def bulk_insert_or_update(self, dataset: list[Dict[str, Any]], _model_, index_field: str = None) -> None:
        if dataset:
            try:
                stmt = pg_insert(_model_)
                if index_field:
                    index_elements = [index_field]
                    values_set = {field: getattr(stmt.excluded, field) for field in dataset[0]}
                    stmt = stmt.on_conflict_do_update(index_elements=index_elements, set_=values_set)
                else:
                    stmt = stmt.on_conflict_do_nothing()

                # async with self.session.begin():
                await self.session.execute(stmt, dataset)
                await self.session.commit()

            except Exception:
                self.logger.error(traceback.format_exc())
                raise DBException()

    async def bulk_update(self, _model_, dataset: list[Dict[str, Any]]) -> None:
        if dataset:
            try:
                stmt = sa.update(_model_)
                await self.session.execute(stmt, dataset)
                await self.session.commit()

            except Exception:
                self.logger.error(traceback.format_exc())
                raise DBException()

    async def save_object(self, obj: Any) -> None:
        try:
            self.session.add(obj)
            await self.session.flush()
            await self.session.commit()

        except IntegrityError:
            raise DBDuplicateException()

        except Exception:
            raise DBException()

        finally:
            self.logger.error(traceback.format_exc())

    async def update_model_instance(self, model_instance, update_data: Dict[str, Any]) -> None:
        try:
            model_instance.update_without_saving(update_data)
            self.session.add(model_instance)
            await self.session.commit()
            await self.session.refresh(model_instance)

        except IntegrityError:
            raise DBDuplicateException()
