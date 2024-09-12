from datetime import date, datetime
from enum import Enum
from typing import List

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models import Base
from src.utils.enums import System


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
        comment="ID карты в системе"
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
        init=False,
        comment="Организация"
    )

    # Организация
    company: Mapped["CompanyOrm"] = relationship(
        back_populates="cards",
        lazy="noload",
        init=False
    )

    belongs_to_car_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.car.id"),
        nullable=True,
        init=False,
        comment="Автомобиль, с которым ассоциирована карта"
    )

    # Автомобиль, с которым ассоциирована карта
    belongs_to_car: Mapped["CarOrm"] = relationship(
        back_populates="cards",
        lazy="noload",
        init=False
    )

    belongs_to_driver_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.user.id"),
        nullable=True,
        init=False,
        comment="Водитель, с которым ассоциирована карта"
    )

    # Водитель, с которым ассоциирована карта
    belongs_to_driver: Mapped["UserOrm"] = relationship(
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

    limit_sum: Mapped[int] = mapped_column(
        sa.SmallInteger(),
        nullable=False,
        server_default=sa.text("0"),
        init=False,
        comment="Лимит (рубли)"
    )

    limit_volume: Mapped[int] = mapped_column(
        sa.SmallInteger(),
        nullable=False,
        server_default=sa.text("0"),
        init=False,
        comment="Лимит (литры)"
    )

    # Список связей этой карты с системами
    card_system_links: Mapped[List["CardSystemOrm"]] = relationship(
        back_populates="card",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список систем, связанных с этой картой
    systems: Mapped[List["SystemOrm"]] = relationship(
        back_populates="cards",
        secondary="cargonomica.card_system",
        viewonly=True,
        lazy="noload",
        init=False
    )

    # Список транзакций, привязанных к этой карте
    transactions: Mapped[List["TransactionOrm"]] = relationship(
        back_populates="card",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список лимитов, привязанных к этой карте
    limits: Mapped[List["CardLimitOrm"]] = relationship(
        back_populates="card",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # История владения картой
    card_history: Mapped[List["CardHistoryOrm"]] = relationship(
        back_populates="card",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    repr_cols = ("card_number",)

    def is_binded_to_system(self, system: System) -> bool:
        for binded_system in self.systems:
            if binded_system.short_name == system.value:
                return True
        return False


class CardHistoryOrm(Base):
    __tablename__ = "card_history"
    __table_args__ = {
        'comment': 'История принадлежности топливных карт'
    }

    # Карта
    card_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.card.id"),
        nullable=False,
        init=True,
        comment="Карта"
    )

    # Карта
    card: Mapped["CardOrm"] = relationship(
        back_populates="card_history",
        lazy="noload",
        init=False
    )

    # Организация
    company_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.company.id"),
        nullable=False,
        init=True,
        comment="Организация"
    )

    # Организация
    company: Mapped["CompanyOrm"] = relationship(
        back_populates="card_history",
        lazy="noload",
        init=False
    )

    begin_time: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=False,
        server_default=sa.text("NOW()"),
        init=False,
        comment="Время начала владения"
    )

    end_time: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=True,
        init=False,
        comment="Время прекращения владения"
    )
