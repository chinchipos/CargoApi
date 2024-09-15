from datetime import date
from typing import List

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base
from src.database.models.overdrafts_history import OverdraftsHistoryOrm
from src.utils.enums import ContractScheme as ContractScheme


class BalanceOrm(Base):
    __tablename__ = "balance"
    __table_args__ = {
        'comment': (
            "Балансы. Для понимания таблицы и ее связей следует рассматривать ее как аналогию с банковскими счетами. "
            "У организации может быть несколько балансов (счетов). Все договоры по перекупной схеме привязаны только к "
            "одному конкретному балансу. Под каждый договор по агентской схеме существует отдельный баланс."
        )
    }

    # Организация
    company_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.company.id"),
        nullable=False,
        init=True,
        comment="Организация"
    )

    # Организация
    company: Mapped["CompanyOrm"] = relationship(
        back_populates="balances",
        lazy="noload",
        init=False
    )

    scheme: Mapped[ContractScheme] = mapped_column(
        ENUM(ContractScheme, name="contractscheme"),
        comment="Схема работы (агентская, перекупная, ...). См. соответствующий public -> Types."
    )

    balance: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False,
        comment="Текущий баланс организации в системе поставщика услуг (актуален для агентской схемы)"
    )

    min_balance: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False,
        comment="Постоянный овердрафт (минимальный баланс)"
    )

    min_balance_period: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False,
        comment="Временный овердрафт (минимальный баланс на период)"
    )

    min_balance_period_end_date: Mapped[date] = mapped_column(
        sa.Date,
        nullable=True,
        init=False,
        comment="Дата прекращения действия временного овердрафта"
    )

    # Список систем, привязанных к этому балансу
    systems: Mapped[List["SystemOrm"]] = relationship(
        back_populates="balances",
        secondary="cargonomica.balance_system",
        viewonly=True,
        lazy="noload",
        init=False
    )

    # Тарифы систем этого баланса
    balance_system: Mapped[List["BalanceSystemOrm"]] = relationship(
        back_populates="balance",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список транзакций, привязанных к этому балансу
    transactions: Mapped[List["TransactionOrm"]] = relationship(
        back_populates="balance",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # История овердрафтов этого баланса
    overdrafts_history: Mapped[List["OverdraftsHistoryOrm"]] = relationship(
        back_populates="balance",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    repr_cols = ("balance", "scheme")

    def __repr__(self) -> str:
        return self.repr(self.repr_cols)
