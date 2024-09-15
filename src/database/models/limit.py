from datetime import datetime
from enum import Enum

import sqlalchemy as sa
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base
from src.database.models.goods_category import GoodsCategory


class Unit(Enum):
    ITEMS = "шт"
    LITERS = "л."
    RUB = "руб"


class LimitPeriod(Enum):
    MONTH = "месяц"
    DAY = "день"


class CardLimitOrm(Base):
    __tablename__ = "card_limit"
    __table_args__ = (
        UniqueConstraint("card_id", "inner_goods_category", "inner_goods_group_id", "period", "unit"),
        {'comment': 'Лимиты по картам'}
    )

    # Система
    system_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.system.id"),
        nullable=False,
        init=True,
        comment="Система"
    )

    # Система
    system: Mapped["SystemOrm"] = relationship(
        back_populates="card_limits",
        init=False,
        lazy="noload"
    )

    external_id: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=True,
        init=False,
        comment="Внешний идентификатор (идентификатор в системе поставщика)"
    )

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
        ENUM(*[item.name for item in Unit], name="unit"),
        nullable=False,
        comment="Единицы измерения"
    )

    period: Mapped[LimitPeriod] = mapped_column(
        ENUM(*[item.name for item in LimitPeriod], name="limitperiod"),
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
        ENUM(*[item.name for item in GoodsCategory], name="goodscategory"),
        nullable=True,
        init=False,
        comment="Категория продуктов в нашей системе"
    )


class GroupLimitOrm(Base):
    __tablename__ = "group_limit"
    __table_args__ = (
        {'comment': ('Таблица для ведения лимитов на группы карт. '
                     'Используется для минимизации количества запросов к API системы поставщика')}
    )

    # Система
    system_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.system.id"),
        nullable=False,
        init=True,
        comment="Система"
    )

    # Система
    system: Mapped["SystemOrm"] = relationship(
        back_populates="group_limits",
        init=False,
        lazy="noload"
    )

    external_id: Mapped[str] = mapped_column(
        sa.String(36),
        nullable=False,
        init=True,
        comment="Внешний ID"
    )

    # Организация
    company_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.company.id"),
        nullable=False,
        init=True,
        comment="Организация"
    )

    # Организация
    company: Mapped["CompanyOrm"] = relationship(
        back_populates="group_limits",
        init=False,
        lazy="noload"
    )

    # Сумма лимита
    limit_sum: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        comment="Сумма лимита"
    )

    # Категория продуктов
    inner_goods_category: Mapped[GoodsCategory] = mapped_column(
        ENUM(*[item.name for item in GoodsCategory], name="goodscategory"),
        nullable=True,
        init=False,
        comment="Категория продуктов в нашей системе"
    )

    # Время установки лимита в системе поставщика
    set_time: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=False,
        server_default=sa.text("NOW()"),
        init=False,
        comment="Время установки лимита в системе поставщика"
    )
