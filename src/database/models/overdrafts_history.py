from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models import Base


class OverdraftsHistoryOrm(Base):
    __tablename__ = "overdrafts_history"
    __table_args__ = {
        'comment': 'История овердрафтов'
    }

    # Баланс
    balance_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.balance.id"),
        nullable=False,
        init=True,
        comment="Баланс"
    )

    # Баланс
    balance: Mapped["BalanceOrm"] = relationship(
        back_populates="overdrafts_history",
        lazy="noload",
        init=False
    )

    days: Mapped[int] = mapped_column(
        sa.Integer(),
        nullable=False,
        init=True,
        comment="Значение параметра [Срок овердрафта, дни] в период пользования услугой"
    )

    sum: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        init=True,
        comment="Значение параметра [Сумма овердрафта] в период пользования услугой"
    )

    begin_date: Mapped[date] = mapped_column(
        sa.Date,
        nullable=False,
        init=True,
        comment='Дата начала пользования услугой "Овердрафт"'
    )

    end_date: Mapped[date] = mapped_column(
        sa.Date,
        nullable=True,
        init=False,
        comment='Дата прекращения пользования услугой "Овердрафт"'
    )
