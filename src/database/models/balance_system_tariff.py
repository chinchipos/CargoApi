import sqlalchemy as sa
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base


class BalanceSystemTariffOrm(Base):
    __tablename__ = "balance_system_tariff"
    __table_args__ = (
        UniqueConstraint("balance_id", "system_id", name="unique_balance_system"),
        {
            'comment': (
                "Сведения из таблицы позволяют указать какой тариф применяется сейчас "
                "при отражении операций с конкретным поставщиком услуг на соответствующем  балансе."
            )
        }
    )

    # Баланс
    balance_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.balance.id"),
        comment="Баланс"
    )

    # Баланс
    balance: Mapped["BalanceOrm"] = relationship(
        back_populates="balance_system_tariff",
        init=False,
        lazy="noload"
    )

    # Поставщиик услуг
    system_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.system.id"),
        nullable=False,
        comment="Поставщиик услуг"
    )

    # Поставщиик услуг
    system: Mapped["SystemOrm"] = relationship(
        back_populates="balance_system_tariff",
        init=False,
        lazy="noload"
    )

    # Тариф
    tariff_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.tariff.id"),
        comment="Тариф"
    )

    # Тариф
    tariff: Mapped["TariffOrm"] = relationship(
        back_populates="balance_system_tariff",
        init=False,
        lazy="noload"
    )
