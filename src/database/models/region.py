from typing import List

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base


class RegionOrm(Base):
    __tablename__ = "region"
    __table_args__ = {
        'comment': 'Регионы'
    }

    name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        unique=True,
        comment="Наименование региона"
    )

    country: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        comment="Страна"
    )

    # Список АЗС этого региона
    azs_stations: Mapped[List["AzsOrm"]] = relationship(
        back_populates="region",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список тарифов, привязанных к этой АЗС
    tariffs: Mapped[List["TariffNewOrm"]] = relationship(
        back_populates="region",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )
