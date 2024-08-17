from datetime import datetime
from typing import List

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base


class LogTypeOrm(Base):
    __tablename__ = "log_type"
    __table_args__ = {
        'comment': 'Типы логов'
    }

    name: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        unique=True,
        comment="Название типа"
    )

    # Список логов этого типа
    logs: Mapped[List["LogOrm"]] = relationship(
        back_populates="log_type",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    repr_cols = ("name",)


class LogOrm(Base):
    __tablename__ = "log"
    __table_args__ = {
        'comment': 'Логирование'
    }

    date_time: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=False,
        server_default=sa.text("NOW()"),
        init=False,
        comment="Время"
    )

    log_type_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.log_type.id"),
        nullable=False,
        comment="Тип лога"
    )

    # Тип лога
    log_type: Mapped["LogTypeOrm"] = relationship(
        back_populates="logs",
        lazy="noload",
        init=False
    )

    message: Mapped[str] = mapped_column(
        sa.String(),
        nullable=False,
        comment="Сообщение"
    )

    details: Mapped[str] = mapped_column(
        sa.String(),
        nullable=False,
        server_default='',
        init=False,
        comment="Подробности"
    )

    username: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        server_default='',
        init=False,
        comment="Имя пользователя"
    )

    previous_state: Mapped[str] = mapped_column(
        sa.String(),
        nullable=False,
        server_default='',
        init=False,
        comment="Предыдущее состояние"
    )

    new_state: Mapped[str] = mapped_column(
        sa.String(),
        nullable=False,
        server_default='',
        init=False,
        comment="Новое состояние"
    )
