from enum import Enum
from typing import Any, List, Dict

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from src.database.models.base import Base


class AzsOwnType(Enum):
    OWN = "Собственная"
    FRANCHISEE = "Франчайзи"
    OPTI = "ОПТИ"
    PARTNER = "Партнер"


class AzsOrm(Base):
    __tablename__ = "azs"
    __table_args__ = (
        sa.UniqueConstraint("system_id", "external_id", name="system_external_id"),
        {'comment': 'АЗС'}
    )

    # Система
    system_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.system.id"),
        nullable=False,
        init=True,
        comment="Система"
    )

    # Система
    system: Mapped["SystemOrm"] = relationship(
        back_populates="azs_list",
        init=False,
        lazy="noload"
    )

    external_id: Mapped[str] = mapped_column(
        sa.String(36),
        nullable=False,
        init=True,
        unique=True,
        comment="Внешний ID"
    )

    name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        init=True,
        comment="Название АЗС"
    )

    address: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        init=True,
        comment="Адрес"
    )

    own_type: Mapped[AzsOwnType] = mapped_column(
        ENUM(*[item.name for item in AzsOwnType], name="azsowntype"),
        nullable=True,
        init=True,
        default=None,
        comment="Тип собственности по отношению к системе"
    )

    # Владелец сети АЗС
    owner_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.azs_owner.id"),
        nullable=True,
        init=False,
        comment="Владелец сети АЗС"
    )

    # Владелец сети АЗС
    owner: Mapped["AzsOwnerOrm"] = relationship(
        back_populates="stations",
        init=False,
        lazy="noload"
    )

    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.sql.true(),
        init=True,
        default=True,
        comment="АЗС осуществляет деятельность"
    )

    # Регион
    region_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.region.id"),
        nullable=True,
        init=True,
        default=None,
        comment="Регион"
    )

    # Регион
    region: Mapped["RegionOrm"] = relationship(
        back_populates="azs_stations",
        init=False,
        lazy="noload"
    )

    latitude: Mapped[float] = mapped_column(
        sa.Numeric(9, 6, asdecimal=False),
        nullable=True,
        init=False,
        comment="Координаты – широта"
    )

    longitude: Mapped[float] = mapped_column(
        sa.Numeric(9, 6, asdecimal=False),
        nullable=True,
        init=False,
        comment="Координаты – долгота"
    )

    timezone: Mapped[str] = mapped_column(
        sa.String(),
        nullable=True,
        init=False,
        comment="Часовой пояс"
    )

    working_time: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=True,
        init=False,
        comment="Время работы"
    )

    # Список тарифов, привязанных к этой АЗС
    tariffs: Mapped[List["TariffNewOrm"]] = relationship(
        back_populates="azs",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список терминалов, привязанных к этой АЗС
    terminals: Mapped[List["TerminalOrm"]] = relationship(
        back_populates="azs",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )


class TerminalOrm(Base):
    __tablename__ = "terminal"
    __table_args__ = {'comment': 'АЗС'}

    external_id: Mapped[str] = mapped_column(
        sa.String(36),
        nullable=False,
        init=True,
        comment="Внешний ID"
    )

    name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=True,
        init=True,
        comment="Наименование терминала"
    )

    # АЗС
    azs_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.azs.id"),
        nullable=False,
        init=True,
        comment="АЗС"
    )

    # АЗС
    azs: Mapped["AzsOrm"] = relationship(
        back_populates="terminals",
        init=False,
        lazy="noload"
    )
