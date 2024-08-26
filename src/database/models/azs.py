from enum import Enum
from typing import Any

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
    __table_args__ = {
        'comment': 'АЗС'
    }

    # Система
    system_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.system.id"),
        nullable=False,
        comment="Система"
    )

    # Система
    system: Mapped["SystemOrm"] = relationship(
        back_populates="azs_list",
        lazy="noload"
    )

    external_id: Mapped[str] = mapped_column(
        sa.String(36),
        nullable=False,
        unique=True,
        comment="Внешний ID"
    )

    name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        comment="Название АЗС"
    )

    code: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        comment="Код АЗС"
    )

    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=True,
        server_default=sa.sql.false(),
        comment="АЗС осуществляет деятельность"
    )

    # Система
    region_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.region.id"),
        nullable=True,
        comment="Регион"
    )

    # Система
    region: Mapped["RegionOrm"] = relationship(
        back_populates="azs_stations",
        lazy="noload"
    )

    address: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        comment="Адрес"
    )

    own_type: Mapped[AzsOwnType] = mapped_column(
        nullable=True,
        comment="Тип собственности по отношению к системе"
    )

    latitude: Mapped[float] = mapped_column(
        sa.Numeric(9, 6, asdecimal=False),
        nullable=True,
        comment="Координаты – широта"
    )

    longitude: Mapped[float] = mapped_column(
        sa.Numeric(9, 6, asdecimal=False),
        nullable=True,
        comment="Координаты – долгота"
    )

    timezone: Mapped[str] = mapped_column(
        sa.String(),
        nullable=True,
        comment="Часовой пояс"
    )

    working_time: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=True,
        comment="Время работы"
    )

    """
    # Список тарифов, привязанных к этой АЗС
    tariffs: Mapped[List["TariffNewOrm"]] = relationship(
        back_populates="azs",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )
    """
