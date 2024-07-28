"""
import copy
from typing import Dict, Any, Tuple

import sqlalchemy as sa
from sqlalchemy import MetaData, inspect
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import MappedAsDataclass, DeclarativeBase, Mapped, mapped_column

from src.config import SCHEMA


class Base(AsyncAttrs, MappedAsDataclass, DeclarativeBase):
    metadata = MetaData(schema=SCHEMA)

    id: Mapped[str] = mapped_column(
        sa.Uuid(as_uuid=False),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
        init=False
    )

    repr_cols = tuple()

    def repr(self, repr_cols: Tuple) -> str:
        # self.date_time.isoformat().replace('T', ' ')
        cols = []
        for idx, col in enumerate(self.__table__.columns.keys()):
            if col in repr_cols:
                cols.append(f"{col}={getattr(self, col)}")

        return f"<{self.__class__.__name__} {', '.join(cols)}>"

    def update_without_saving(self, data: Dict[str, Any]) -> None:
        for field, value in data.items():
            setattr(self, field, value)

    def dumps(self) -> Dict[str, Any]:
        # Формируем словарь, состоящий из полей модели
        dump = {column.key: getattr(self, column.key) for column in inspect(self).mapper.column_attrs}

        # Добавляем в словарь связанные модели
        relationships = inspect(self.__class__).relationships
        for rel in relationships:
            try:
                dump[rel.key] = getattr(self, rel.key)

            finally:
                pass

        return dump

    def annotate(self, data: Dict[str, Any]) -> Any:
        for field, value in data.items():
            setattr(self, field, copy.deepcopy(value))
        return self
"""
