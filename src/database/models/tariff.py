from datetime import datetime
from typing import List

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base
from src.database.models.goods_category import GoodsCategory


class TariffOrm(Base):
    __tablename__ = "tariff"
    __table_args__ = {
        'comment': 'Тарифы'
    }

    master_db_id: Mapped[int] = mapped_column(
        sa.Integer(),
        nullable=True,
        init=False,
        comment="Идентификатор в боевой БД (для синхронизации)"
    )

    name: Mapped[str] = mapped_column(
        sa.String(50),
        unique=True,
        nullable=False,
        comment="Название"
    )

    fee_percent: Mapped[float] = mapped_column(
        sa.Numeric(5, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        comment="Комиссия, %"
    )

    # Список транзакций по этому тарифу
    transactions: Mapped[List["TransactionOrm"]] = relationship(
        back_populates="tariff",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Текущие связки Баланс-Система, для которых применяется этот тариф
    balance_system_tariff: Mapped[List["BalanceSystemTariffOrm"]] = relationship(
        back_populates="tariff",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # История связок Баланс-Система, для которых применялся или применяется этот тариф
    balance_tariff_history: Mapped[List["BalanceTariffHistoryOrm"]] = relationship(
        back_populates="tariff",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )


class TariffPolicyOrm(Base):
    __tablename__ = "tariff_policy"
    __table_args__ = {
        'comment': 'Тарифные политики'
    }

    name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        comment="Наименование"
    )

    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.sql.false(),
        comment="Политика активна"
    )

    # Список тарифов, привязанных к этой политике
    tariffs: Mapped[List["TariffNewOrm"]] = relationship(
        back_populates="policy",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )


class TariffNewOrm(Base):
    __tablename__ = "tariff_new"
    __table_args__ = (
        sa.UniqueConstraint(
            "policy_id",
            "system_id",
            "inner_goods_group_id",
            "inner_goods_category",
            "azs_id",
            "end_time"
        ),
        {'comment': 'Тарифы'}
    )

    # Тарифная политика
    policy_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.tariff_policy.id"),
        nullable=False,
        comment="Тарифная политика"
    )

    # Тарифная политика
    policy: Mapped["TariffPolicyOrm"] = relationship(
        back_populates="tariffs",
        lazy="noload"
    )

    # Система
    system_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.system.id"),
        nullable=False,
        comment="Система"
    )

    # Система
    system: Mapped["SystemOrm"] = relationship(
        back_populates="tariffs",
        lazy="noload"
    )

    # Группа продуктов
    inner_goods_group_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.inner_goods_group.id"),
        nullable=True,
        comment="Группа продуктов в нашей системе"
    )

    # Группа продуктов
    inner_goods_group: Mapped["InnerGoodsGroupOrm"] = relationship(
        back_populates="tariffs",
        lazy="noload"
    )

    # Категория продуктов
    inner_goods_category: Mapped[GoodsCategory] = mapped_column(
        nullable=True,
        init=False,
        comment="Категория продуктов в нашей системе"
    )

    # АЗС
    azs_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.azs.id"),
        nullable=True,
        comment="АЗС"
    )

    # АЗС
    azs: Mapped["AzsOrm"] = relationship(
        back_populates="tariffs",
        lazy="noload"
    )

    discount_fee_percent: Mapped[float] = mapped_column(
        sa.Numeric(4, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        comment="Процент скидки/наценки"
    )

    begin_time: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=False,
        server_default=sa.text("NOW()"),
        comment="Время начала действия"
    )

    end_time: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=True,
        comment="Время прекращения действия"
    )
