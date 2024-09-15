from typing import List

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ENUM

from src.database.models.base import Base
from src.database.models.limit import Unit
from src.database.models.goods_category import GoodsCategory


class InnerGoodsGroupOrm(Base):
    __tablename__ = "inner_goods_group"
    __table_args__ = {
        'comment': 'Группы продуктов в нашей системе'
    }

    name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=True,
        init=False,
        comment="Наименование группы"
    )

    inner_category: Mapped[GoodsCategory] = mapped_column(
        ENUM(*[item.name for item in GoodsCategory], name="goodscategory"),
        nullable=True,
        init=False,
        comment="Категория продуктов в нашей системе"
    )

    base_unit: Mapped[Unit] = mapped_column(
        ENUM(*[item.name for item in Unit], name="unit"),
        nullable=True,
        init=False,
        comment="Базовая единица измерения (кроме рублей)"
    )

    # Список групп продуктов от систем поставщиков, привязанных к этой группе нашей системы
    outer_goods_groups: Mapped[List["OuterGoodsGroupOrm"]] = relationship(
        back_populates="inner_group",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список лимитов, привязанных к этой группе нашей системы
    limits: Mapped[List["CardLimitOrm"]] = relationship(
        back_populates="inner_goods_group",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список тарифов, привязанных к этой группе нашей системы
    tariffs: Mapped[List["TariffNewOrm"]] = relationship(
        back_populates="inner_goods_group",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    def get_outer_goods_group(self, system_id: str):
        for group in self.outer_goods_groups:
            if group.system_id == system_id:
                return group


class OuterGoodsGroupOrm(Base):
    __tablename__ = "outer_goods_group"
    __table_args__ = {
        'comment': 'Группы продуктов в системах поставщиков'
    }

    external_id: Mapped[str] = mapped_column(
        sa.String(36),
        nullable=True,
        init=False,
        unique=True,
        comment="ID группы продуктов в системе поставщика"
    )

    name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=True,
        init=False,
        comment="Наименование группы продуктов в системе поставщика"
    )

    system_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.system.id"),
        nullable=False,
        init=True,
        comment="Система"
    )

    # Система
    system: Mapped["SystemOrm"] = relationship(
        back_populates="outer_goods_groups",
        lazy="noload"
    )

    # Соответствующая категория продуктов в системе поставщика
    outer_category_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.outer_goods_category.id"),
        nullable=False,
        init=True,
        comment="Соответствующая категория продуктов в системе поставщика"
    )

    # Соответствующая категория продуктов в системе поставщика
    outer_category: Mapped["OuterGoodsCategoryOrm"] = relationship(
        back_populates="outer_goods_groups",
        lazy="noload"
    )

    # Соответствующая группа продуктов в нашей системе
    inner_group_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.inner_goods_group.id"),
        nullable=True,
        init=True,
        comment="Соответствующая группа продуктов в нашей системе"
    )

    # Соответствующая группа продуктов в нашей системе
    inner_group: Mapped["InnerGoodsGroupOrm"] = relationship(
        back_populates="outer_goods_groups",
        lazy="noload"
    )

    # Список продуктов, привязанных к этой группе продуктов
    outer_goods: Mapped[List["OuterGoodsOrm"]] = relationship(
        back_populates="outer_group",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )
