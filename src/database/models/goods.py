from typing import List

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base


class InnerGoodsOrm(Base):
    __tablename__ = "inner_goods"
    __table_args__ = {
        'comment': 'Продукты в нашей системе'
    }

    name: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        unique=True,
        comment="Наименование в нашей системе"
    )

    # Список внешних товаров и услуг, привязанных к этой номенклатуре внутренних товаров/услуг
    outer_goods: Mapped[List["OuterGoodsOrm"]] = relationship(
        back_populates="inner_goods",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )


class OuterGoodsOrm(Base):
    __tablename__ = "outer_goods"
    __table_args__ = (
        {'comment': 'Продукты в системах поставщиков'}
    )

    # ID продукта в системе
    external_id: Mapped[str] = mapped_column(
        sa.String(36),
        nullable=True,
        init=False,
        unique=True,
        comment="ID продукта в системе поставщика"
    )

    # Наименование продукта в системе поставщика
    name: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        comment="Наименование продукта в системе поставщика"
    )

    # Система
    system_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.system.id"),
        nullable=False,
        comment="Система"
    )

    # Система
    system: Mapped["SystemOrm"] = relationship(
        back_populates="outer_goods",
        lazy="noload"
    )

    outer_group_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.outer_goods_group.id"),
        nullable=True,
        init=False,
        comment="Соответствующая группа продукта в системе поставщика"
    )

    outer_group: Mapped["OuterGoodsGroupOrm"] = relationship(
        back_populates="outer_goods",
        lazy="noload",
        init=False
    )

    inner_goods_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.inner_goods.id"),
        nullable=True,
        init=False,
        comment="Соответствующий продукт в нашей системе"
    )

    inner_goods: Mapped["InnerGoodsOrm"] = relationship(
        back_populates="outer_goods",
        lazy="noload",
        init=False
    )

    # Список транзакций, привязанных к этому продукту
    transactions: Mapped[List["TransactionOrm"]] = relationship(
        back_populates="outer_goods",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )
