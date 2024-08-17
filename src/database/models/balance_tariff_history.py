from datetime import date

import sqlalchemy as sa
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base


class BalanceTariffHistoryOrm(Base):
    __tablename__ = "balance_tariff_history"
    __table_args__ = (
        UniqueConstraint("balance_id", "system_id", "tariff_id", "start_date", name="unique_balance_sys_tariff_start"),
        UniqueConstraint("balance_id", "system_id", "tariff_id", "end_date", name="unique_balance_sys_tariff_end"),
        {
            'comment': (
                "Сведения из таблицы позволяют узнать какой тариф применялся ранее и применяется сейчас "
                "при отражении операций с конкретным поставщиком услуг на соответствующем  балансе."
            )
        }
    )

    # Баланс
    balance_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.balance.id"),
        comment="Баланс"
    )

    # Поставщиик услуг
    system_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.system.id"),
        nullable=False,
        comment="Поставщиик услуг"
    )

    # Тариф
    tariff_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.tariff.id"),
        comment="Тариф"
    )

    # Тариф
    tariff: Mapped["TariffOrm"] = relationship(
        back_populates="balance_tariff_history",
        lazy="noload"
    )

    # Дата начала действия (тариф действует с 00:00:00 в указанную дату)
    start_date: Mapped[date] = mapped_column(
        sa.Date,
        nullable=False,
        server_default=sa.text("NOW()"),
        comment="Дата начала действия (тариф действует с 00:00:00 в указанную дату)"
    )

    # Дата прекращения действия (тариф прекращает действовать с 00:00:00 в указанную дату)
    end_date: Mapped[date] = mapped_column(
        sa.Date,
        nullable=True,
        init=False,
        comment="Дата прекращения действия (тариф прекращает действовать с 00:00:00 в указанную дату)"
    )
