import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models import Base


class CardGroupOrm(Base):
    __tablename__ = "card_group"
    __table_args__ = {
        'comment': 'Группы карт'
    }

    # Система
    system_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.system.id"),
        nullable=False,
        init=True,
        comment="Система"
    )

    # Система
    system: Mapped["SystemOrm"] = relationship(
        back_populates="card_groups",
        init=False,
        lazy="noload"
    )

    external_id: Mapped[str] = mapped_column(
        sa.String(),
        nullable=False,
        init=True,
        comment="Идентификатор во внешней системе"
    )

    name: Mapped[str] = mapped_column(
        sa.String(50),
        unique=True,
        nullable=False,
        comment="Название группы"
    )

    # Организация
    company_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.company.id"),
        nullable=False,
        init=True,
        comment="Организация"
    )

    # Организация
    company: Mapped["CompanyOrm"] = relationship(
        back_populates="card_groups",
        init=False,
        lazy="noload"
    )

    repr_cols = ("name",)
