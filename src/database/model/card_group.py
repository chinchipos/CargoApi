from typing import List

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.model import Base


class CardGroupOrm(Base):
    __tablename__ = "card_group"
    __table_args__ = {
        'comment': 'Группы карт'
    }

    external_id: Mapped[str] = mapped_column(
        sa.String(),
        nullable=False,
        init=True,
        comment="Идентификатор во внешней системе"
    )

    name: Mapped[str] = mapped_column(
        sa.String(50),
        unique=True,
        nullable=False,
        comment="Название группы"
    )

    # Список карт этой группы
    cards: Mapped[List["CardOrm"]] = relationship(
        back_populates="card_group",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    repr_cols = ("name",)
