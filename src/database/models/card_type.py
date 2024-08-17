from typing import List

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models import Base


class CardTypeOrm(Base):
    __tablename__ = "card_type"
    __table_args__ = {
        'comment': 'Типы карт'
    }

    name: Mapped[str] = mapped_column(
        sa.String(50),
        unique=True,
        nullable=False,
        comment="Название типа"
    )

    # Список карт этого типа
    cards: Mapped[List["CardOrm"]] = relationship(
        back_populates="card_type",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    repr_cols = ("name",)
