from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base
from src.utils.enums import Bank


class MoneyReceiptOrm(Base):
    __tablename__ = "money_receipt"
    __table_args__ = (
        UniqueConstraint("payment_id", "payment_date_time", "amount", name="uniq_pmntid_time_amount"),
        {
            'comment': (
                "Автозачисления денежных средств на балансы организаций"
            )
        }
    )

    bank: Mapped[Bank] = mapped_column(
        ENUM(*[item.name for item in Bank], name="bank"),
        comment="Банк",
        init=True,
    )

    payment_id: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=True,
        init=False,
        comment="Идентификатор операции (транзакции), присвоенный банком"
    )

    payment_date_time: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=False,
        init=True,
        comment="Время выполнения проводки банком (по выписке)"
    )

    payment_company_name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        init=True,
        comment="Наименование организации (по выписке)"
    )

    payment_company_inn: Mapped[str] = mapped_column(
        sa.String(12),
        nullable=False,
        init=True,
        comment="ИНН организации (по выписке)"
    )

    payment_purpose: Mapped[str] = mapped_column(
        sa.String(210),
        nullable=False,
        init=True,
        comment="Назначение платежа"
    )

    amount: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        init=True,
        comment="Сумма платежа"
    )

    # Локальная транзакция
    transaction_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.transaction.id"),
        nullable=True,
        init=False,
        comment="Локальная транзакция"
    )

    # Локальная транзакция
    transaction: Mapped["TransactionOrm"] = relationship(
        back_populates="money_receipt",
        lazy="noload",
        init=False
    )