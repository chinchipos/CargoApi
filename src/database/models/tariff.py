from typing import List

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base


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
