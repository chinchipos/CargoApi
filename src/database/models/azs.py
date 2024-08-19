from datetime import time
from typing import List

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base


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

    name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        comment="Название АЗС"
    )

    code: Mapped[str] = mapped_column(
        sa.String(30),
        nullable=False,
        comment="Код АЗС"
    )

    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=True,
        server_default=sa.sql.false(),
        comment="АЗС работает"
    )

    country_code: Mapped[str] = mapped_column(
        sa.String(3),
        nullable=True,
        comment="Код страны"
    )

    region_code: Mapped[str] = mapped_column(
        sa.String(10),
        nullable=True,
        comment="Код региона"
    )

    address: Mapped[str] = mapped_column(
        sa.String(),
        nullable=False,
        comment="Адрес"
    )

    is_franchisee: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=True,
        server_default=sa.sql.false(),
        comment="Франчайзи"
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

    timezone: Mapped[int] = mapped_column(
        sa.Integer(),
        nullable=True,
        comment="Часовой пояс"
    )

    working_days: Mapped[str] = mapped_column(
        sa.String(7),
        nullable=True,
        comment="Рабочие дни"
    )

    begin_work_time: Mapped[time] = mapped_column(
        sa.Time,
        nullable=True,
        comment="Время открытия"
    )

    end_work_time: Mapped[time] = mapped_column(
        sa.Time,
        nullable=True,
        comment="Время закрытия"
    )

    # Список тарифов, привязанных к этой АЗС
    tariffs: Mapped[List["TariffNewOrm"]] = relationship(
        back_populates="azs",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )