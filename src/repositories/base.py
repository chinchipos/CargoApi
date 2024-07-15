from typing import Dict, Any

import sqlalchemy as sa
import sqlalchemy.exc
import sqlparse
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from src.database import models
from src.database.db import get_session

from src.utils.exceptions import DBException, DBDuplicateException, BadRequestException, api_logger

import traceback


class BaseRepository:

    def __init__(self, session: get_session, user: models.User | None = None):
        self.session = session
        self.user = user
        self.logger = api_logger

    @staticmethod
    def statement(stmt) -> None:
        print(sqlparse.format(str(stmt.compile()), reindent=True))

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

    async def delete_object(self, _model_, _id_: str, silent: bool = False):
        try:
            stmt = sa.delete(_model_).where(_model_.id == _id_)
            await self.session.execute(stmt)
            await self.session.commit()

        except sqlalchemy.exc.IntegrityError:
            if silent:
                pass
            else:
                self.logger.error(traceback.format_exc())
                raise BadRequestException("Невозможно удалить объект, так как на него ссылаются другие записи")

        except Exception:
            if silent:
                pass
            else:
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

    async def insert(self, _model_, **fields) -> Any:
        try:
            stmt = pg_insert(_model_).values(fields)
            result = await self.session.scalars(
                stmt.returning(_model_),
                execution_options={"populate_existing": True}
            )
            await self.session.commit()
            return result.first()

        except sa.exc.IntegrityError:
            self.logger.error(traceback.format_exc())
            raise DBDuplicateException()

        except Exception:
            self.logger.error(traceback.format_exc())
            raise DBException()

    async def insert_or_update(self, _model_, index_field, **set_fields) -> Any:
        try:
            stmt = pg_insert(_model_).values(set_fields)
            index_elements = [index_field]
            values_set = {field: getattr(stmt.excluded, field) for field in set_fields}
            stmt = stmt.on_conflict_do_update(index_elements=index_elements, set_=values_set)
            result = await self.session.scalars(
                stmt.returning(_model_),
                execution_options={"populate_existing": True}
            )
            await self.session.commit()
            return result.first()

        except Exception:
            self.logger.error(traceback.format_exc())
            raise DBException()

    async def bulk_insert_or_update(self, _model_, dataset: list[Dict[str, Any]], index_field: str = None) -> None:
        if dataset:
            try:
                stmt = pg_insert(_model_)
                if index_field:
                    index_elements = [index_field]
                    values_set = {field: getattr(stmt.excluded, field) for field in dataset[0]}
                    stmt = stmt.on_conflict_do_update(index_elements=index_elements, set_=values_set)
                else:
                    stmt = stmt.on_conflict_do_nothing()

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
            # Удалим объект из сессии, так как в кэше хранятся связанные объекты и при обновлении информации
            # об объекте из БД связанные объекты не будут обновлены, вместо этого будут взяты из кэша.
            # self.session.expire(obj)
            await self.session.refresh(obj)
            # self.session.expire_all()
            # https://stackoverflow.com/questions/12108913/how-to-avoid-caching-in-sqlalchemy

        except IntegrityError:
            self.logger.error(traceback.format_exc())
            raise DBDuplicateException()

        except Exception:
            self.logger.error(traceback.format_exc())
            raise DBException()

    async def update_object(self, obj, update_data: Dict[str, Any]) -> None:
        try:
            obj.update_without_saving(update_data)
            await self.save_object(obj)

        except IntegrityError:
            self.logger.error(traceback.format_exc())
            raise DBDuplicateException()

        except Exception:
            self.logger.error(traceback.format_exc())
            raise DBException()
