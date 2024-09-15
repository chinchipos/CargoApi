from datetime import datetime
from typing import List

import sqlalchemy as sa
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base
from src.utils.enums import ContractScheme


class SystemOrm(Base):
    __tablename__ = "system"
    __table_args__ = {
        'comment': 'Поставщики услуг'
    }

    master_db_id: Mapped[int] = mapped_column(
        sa.Integer(),
        nullable=True,
        init=False,
        comment="Идентификатор в боевой БД (для синхронизации)"
    )

    full_name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        unique=True,
        init=True,
        comment="Полное наименование организации"
    )

    short_name: Mapped[str] = mapped_column(
        sa.String(30),
        nullable=False,
        unique=True,
        init=True,
        comment="Сокращенное наименование организации"
    )

    balance: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False,
        comment="Наш текущий баланс в системе поставщика услуг (актуален для перекупной схемы)"
    )

    transaction_days: Mapped[int] = mapped_column(
        sa.SmallInteger(),
        nullable=False,
        server_default=sa.text("50"),
        init=False,
        comment="Период, за который запрашиваются транзакции при синхронизации"
    )

    scheme: Mapped[ContractScheme] = mapped_column(
        ENUM(*[item.name for item in ContractScheme], name="contractscheme"),
        comment="Схема работы (агентская, перекупная, ...). См. соответствующий public -> Types.",
        init=True,
        server_default=ContractScheme.OVERBOUGHT.name
    )

    limits_on: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.sql.true(),
        init=False,
        comment='Признак - в системе доступна функция установки лимитов'
    )

    enabled: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.sql.true(),
        init=False,
        comment='Признак - с системой заключен договор, можно в ней обслуживаться на текущий момент'
    )

    transactions_sync_dt: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=True,
        init=False,
        comment="Дата последней успешной синхронизаци транзакций"
    )

    cards_sync_dt: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=True,
        init=False,
        comment="Дата последней успешной синхронизации карт"
    )

    balance_sync_dt: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=True,
        init=False,
        comment="Дата последней успешной синхронизации баланса"
    )

    card_icon_url: Mapped[str] = mapped_column(
        sa.String(),
        nullable=True,
        init=False,
        comment="Ссылка на иконку карты"
    )

    # Список балансов, связанных с этой системой
    balances: Mapped[List["BalanceOrm"]] = relationship(
        back_populates="systems",
        secondary="cargonomica.balance_system",
        viewonly=True,
        lazy="noload",
        init=False
    )

    # Список карт, связанных с этой системой
    cards: Mapped[List["CardOrm"]] = relationship(
        back_populates="systems",
        secondary="cargonomica.card_system",
        viewonly=True,
        lazy="noload",
        init=False
    )

    # Список договоров, привязанных к этой системе
    balance_system: Mapped[List["BalanceSystemOrm"]] = relationship(
        back_populates="system",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список транзакций, привязанных к этой системе
    transactions: Mapped[List["TransactionOrm"]] = relationship(
        back_populates="system",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список товаров и услуг, привязанных к этой системе
    outer_goods: Mapped[List["OuterGoodsOrm"]] = relationship(
        back_populates="system",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список групп товаров, привязанных к этой системе
    outer_goods_groups: Mapped[List["OuterGoodsGroupOrm"]] = relationship(
        back_populates="system",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список категорий товаров, привязанных к этой системе
    outer_goods_categories: Mapped[List["OuterGoodsCategoryOrm"]] = relationship(
        back_populates="system",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список тарифов, привязанных к этой системе
    tariffs: Mapped[List["TariffNewOrm"]] = relationship(
        back_populates="system",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список АЗС этой системы
    azs_list: Mapped[List["AzsOrm"]] = relationship(
        back_populates="system",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список карточных групп этой системы
    card_groups: Mapped[List["CardGroupOrm"]] = relationship(
        back_populates="system",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список карточных лимитов этой системы
    card_limits: Mapped[List["CardLimitOrm"]] = relationship(
        back_populates="system",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список групповых лимитов этой системы
    group_limits: Mapped[List["GroupLimitOrm"]] = relationship(
        back_populates="system",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    repr_cols = ("full_name",)

    def __repr__(self) -> str:
        return self.repr(self.repr_cols)


class CardSystemOrm(Base):
    __tablename__ = "card_system"
    __table_args__ = (
        UniqueConstraint("card_id", "system_id", name="unique_card_system"),
        {
            'comment': "Сведения из таблицы указывают к какой системе привязана карта"
        }
    )

    # Карта
    card_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.card.id"),
        nullable=False,
        comment="Карта"
    )

    # Карта
    card: Mapped["CardOrm"] = relationship(
        back_populates="card_system_links",
        lazy="noload"
    )

    # Система
    system_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.system.id"),
        nullable=False,
        comment="Поставщиик услуг"
    )

    repr_cols = ("card_id",)
