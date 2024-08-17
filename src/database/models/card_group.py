from typing import List

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models import Base


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

    repr_cols = ("name",)
