from enum import Enum

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base
from src.database.models.goods_category import GoodsCategory


class Unit(Enum):
    ITEMS = "шт"
    LITERS = "л."
    RUB = "руб."


class LimitPeriod(Enum):
    DAY = "день"
    MONTH = "месяц"


class CardLimitOrm(Base):
    __tablename__ = "card_limit"
    __table_args__ = {
        'comment': 'Лимиты по картам'
    }

    # Карта
    card_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.card.id"),
        nullable=False,
        comment="Карта"
    )

    # Карта
    card: Mapped["CardOrm"] = relationship(
        back_populates="limits",
        lazy="noload"
    )

    value: Mapped[int] = mapped_column(
        sa.Integer(),
        nullable=False,
        server_default=sa.text("0"),
        comment="Значение лимита"
    )

    unit: Mapped[Unit] = mapped_column(
        nullable=False,
        comment="Единицы измерения"
    )

    period: Mapped[LimitPeriod] = mapped_column(
        nullable=False,
        comment="Период обнуления лимита"
    )

    # Группа продуктов
    inner_goods_group_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.inner_goods_group.id"),
        nullable=True,
        comment="Группа продуктов в нашей системе"
    )

    # Группа продуктов
    inner_goods_group: Mapped["InnerGoodsGroupOrm"] = relationship(
        back_populates="limits",
        lazy="noload"
    )

    # Категория продуктов
    inner_goods_category: Mapped[GoodsCategory] = mapped_column(
        nullable=True,
        init=False,
        comment="Категория продуктов в нашей системе"
    )
