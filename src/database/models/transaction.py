from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base
from src.utils.enums import TransactionType


class TransactionOrm(Base):
    __tablename__ = "transaction"
    __table_args__ = (
        sa.UniqueConstraint("date_time", "balance_id", "transaction_sum"),
        {'comment': 'Транзакции'}
    )

    master_db_id: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        server_default="",
        init=False,
        comment="Идентификатор в боевой БД (для синхронизации)"
    )

    external_id: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        server_default="",
        init=False,
        comment="Внешний идентификатор (идентификатор в системе поставщика услуг)"
    )

    date_time: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=False,
        comment="Время совершения транзакции"
    )

    date_time_load: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=False,
        init=False,
        comment="Время прогрузки в БД"
    )

    transaction_type: Mapped[TransactionType] = mapped_column(
        ENUM(TransactionType, name="transactiontype"),
        comment="Тип транзакции"
    )

    # Карта
    card_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.card.id"),
        nullable=True,
        comment="Карта"
    )

    # Карта
    card: Mapped["CardOrm"] = relationship(
        back_populates="transactions",
        lazy="noload"
    )

    # Баланс
    balance_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.balance.id"),
        nullable=True,
        comment="Карта"
    )

    # Баланс
    balance: Mapped["BalanceOrm"] = relationship(
        back_populates="transactions",
        lazy="noload"
    )

    # Поставщик услуг
    system_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.system.id"),
        nullable=True,
        comment="Поставщик услуг"
    )

    # Баланс
    system: Mapped["SystemOrm"] = relationship(
        back_populates="transactions",
        lazy="noload"
    )

    azs_code: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        server_default="",
        init=False,
        comment="Код АЗС"
    )

    outer_goods_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.outer_goods.id"),
        nullable=True,
        comment="Товар/услуга"
    )

    # Товар/услуга
    outer_goods: Mapped["OuterGoodsOrm"] = relationship(
        back_populates="transactions",
        lazy="noload"
    )

    fuel_volume: Mapped[float] = mapped_column(
        sa.Float(),
        nullable=False,
        server_default=sa.text("0"),
        init=False,
        comment="Литры"
    )

    price: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False,
        comment="Цена"
    )

    transaction_sum: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False,
        comment="Сумма по транзакции"
    )

    discount_sum: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False,
        comment="Скидка"
    )

    tariff_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.tariff.id"),
        nullable=True,
        comment="Тариф"
    )

    tariff_new_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.tariff_new.id"),
        nullable=True,
        comment="Тариф"
    )

    # Тариф
    tariff_new: Mapped["TariffNewOrm"] = relationship(
        back_populates="transactions",
        lazy="noload"
    )

    fee_sum: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False,
        comment="Сумма комиссионного вознаграждения по тарифу"
    )

    total_sum: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False,
        comment="Итоговая сумма для применения к балансу организации"
    )

    company_balance: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False,
        comment="Баланс организации после выполнения транзакции"
    )

    comments: Mapped[str] = mapped_column(
        sa.String(),
        nullable=False,
        server_default="",
        comment="Комментарии"
    )

    # Список автозачислений ДС этой организации
    money_receipt: Mapped["MoneyReceiptOrm"] = relationship(
        back_populates="transaction",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    repr_cols = ("id", "transaction_sum", "date_time")
