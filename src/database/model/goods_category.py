from enum import Enum
from typing import List

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.model.base import Base


class GoodsCategory(Enum):
    FOOD = "FOOD"
    CAFE = "CAFE"
    NON_FOOD = "NON_FOOD"
    OTHER_SERVICES = "OTHER_SERVICES"
    ROAD_PAYING = "ROAD_PAYING"
    FUEL = "FUEL"


class OuterGoodsCategoryOrm(Base):
    __tablename__ = "outer_goods_category"
    __table_args__ = {
        'comment': 'Категории продуктов в системах поставщиков'
    }

    external_id: Mapped[str] = mapped_column(
        sa.String(36),
        nullable=True,
        init=False,
        unique=True,
        comment="ID категории продуктов в системе поставщика"
    )

    name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=True,
        init=False,
        comment="Наименование категории продуктов"
    )

    system_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.system.id"),
        nullable=False,
        init=True,
        comment="Система"
    )

    # Система
    system: Mapped["System"] = relationship(
        back_populates="outer_goods_categories",
        lazy="noload"
    )

    inner_category: Mapped[GoodsCategory] = mapped_column(
        nullable=True,
        init=False,
        comment="Соответствующая категория продуктов в нашей системе"
    )

    # Список групп товаров, привязанных к этой категории
    outer_goods_groups: Mapped[List["OuterGoodsGroupOrm"]] = relationship(
        back_populates="outer_category",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )
