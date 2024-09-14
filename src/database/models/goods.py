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


class OuterGoodsOrm(Base):
    __tablename__ = "outer_goods"
    __table_args__ = (
        {'comment': 'Продукты в системах поставщиков'}
    )

    # ID продукта в системе
    external_id: Mapped[str] = mapped_column(
        sa.String(36),
        nullable=True,
        init=True,
        unique=True,
        comment="ID продукта в системе поставщика"
    )

    # Наименование продукта в системе поставщика
    name: Mapped[str] = mapped_column(
        sa.String(255),
        init=True,
        nullable=False,
        comment="Наименование продукта в системе поставщика"
    )

    # Наименование продукта в нашей системе
    inner_name: Mapped[str] = mapped_column(
        sa.String(255),
        init=False,
        nullable=True,
        comment="Наименование продукта в нашей системе"
    )

    # Система
    system_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.system.id"),
        init=True,
        nullable=False,
        comment="Система"
    )

    # Система
    system: Mapped["SystemOrm"] = relationship(
        back_populates="outer_goods",
        init=False,
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

    # Список транзакций, привязанных к этому продукту
    transactions: Mapped[List["TransactionOrm"]] = relationship(
        back_populates="outer_goods",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )
