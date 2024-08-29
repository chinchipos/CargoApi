import sqlalchemy as sa
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base


class BalanceSystemOrm(Base):
    __tablename__ = "balance_system"
    __table_args__ = (
        UniqueConstraint("balance_id", "system_id", name="unique_balance_system"),
        {
            'comment': (
                "Связи Баланс <-> Система"
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
        back_populates="balance_system",
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
        back_populates="balance_system",
        init=False,
        lazy="noload"
    )
