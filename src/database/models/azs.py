from enum import Enum
from typing import Any, List

import sqlalchemy as sa
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
        comment="Внешний ID"
    )

    name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        init=True,
        comment="Название АЗС"
    )

    code: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        init=True,
        comment="Код АЗС"
    )

    address: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        init=True,
        comment="Адрес"
    )

    own_type: Mapped[AzsOwnType] = mapped_column(
        nullable=True,
        init=True,
        default=None,
        comment="Тип собственности по отношению к системе"
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
