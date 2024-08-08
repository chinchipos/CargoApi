from datetime import date
from enum import Enum
from typing import List

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.model import Base


class BlockingCardReason(Enum):
    MANUALLY = "Блокировка ННК"
    NNK = "Заблокировано ННК"
    COMPANY = "Заблокировано организацией"
    PIN = "Блокировка по ПИН"


class CardOrm(Base):
    __tablename__ = "card"
    __table_args__ = {
        'comment': 'Карты'
    }

    external_id: Mapped[str] = mapped_column(
        sa.String(30),
        nullable=True,
        comment="ID арты в системе"
    )

    card_number: Mapped[str] = mapped_column(
        sa.String(20),
        unique=True,
        nullable=False,
        comment="Номер карты"
    )

    card_type_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.card_type.id"),
        comment="Тип карты"
    )

    # Тип карты
    card_type: Mapped["CardTypeOrm"] = relationship(
        back_populates="cards",
        lazy="noload",
        init=False
    )

    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.sql.false(),
        comment="Карта активна"
    )

    reason_for_blocking: Mapped[BlockingCardReason] = mapped_column(
        comment="Причина блокировки карты",
        nullable=True,
        init=False
    )

    # Организация
    company_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.company.id"),
        nullable=True,
        init=True,
        comment="Организация"
    )

    # Организация
    company: Mapped["Company"] = relationship(
        back_populates="cards",
        lazy="noload",
        init=False
    )

    belongs_to_car_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.car.id"),
        nullable=True,
        comment="Автомобиль, с которым ассоциирована карта"
    )

    # Автомобиль, с которым ассоциирована карта
    belongs_to_car: Mapped["Car"] = relationship(
        back_populates="cards",
        lazy="noload",
        init=False
    )

    belongs_to_driver_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.user.id"),
        nullable=True,
        comment="Водитель, с которым ассоциирована карта"
    )

    # Водитель, с которым ассоциирована карта
    belongs_to_driver: Mapped["User"] = relationship(
        back_populates="cards",
        lazy="noload",
        init=False
    )

    date_last_use: Mapped[date] = mapped_column(
        sa.Date,
        nullable=True,
        init=False,
        comment="Дата последнего использования"
    )

    # Группа
    group_id: Mapped[str] = mapped_column(
        sa.String(30),
        nullable=True,
        comment="ID группы в системе"
    )

    # Список связей этой карты с системами
    card_system_links: Mapped[List["CardSystem"]] = relationship(
        back_populates="card",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список систем, связанных с этой картой
    systems: Mapped[List["System"]] = relationship(
        back_populates="cards",
        secondary="cargonomica.card_system",
        viewonly=True,
        lazy="noload",
        init=False
    )

    # Список транзакций, привязанных к этой карте
    transactions: Mapped[List["Transaction"]] = relationship(
        back_populates="card",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    repr_cols = ("card_number",)
