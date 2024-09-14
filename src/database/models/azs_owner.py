from typing import List

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base


class AzsOwnerOrm(Base):
    __tablename__ = "azs_owner"
    __table_args__ = {'comment': 'Владельцы АЗС (сети ТО)'}

    name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        unique=True,
        init=True,
        comment="Наименование владельца сети АЗС"
    )

    # Список АЗС этой сети
    stations: Mapped[List["AzsOrm"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )
