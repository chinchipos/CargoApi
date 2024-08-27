from datetime import date
from typing import List

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base
from src.database.models.balance import BalanceOrm


class CompanyOrm(Base):
    __tablename__ = "company"
    __table_args__ = {
        'comment': 'Организации'
    }

    master_db_id: Mapped[int] = mapped_column(
        sa.Integer(),
        nullable=True,
        init=False,
        comment="Идентификатор в боевой БД (для синхронизации)"
    )

    name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        comment="Наименование организации"
    )

    inn: Mapped[str] = mapped_column(
        sa.String(12),
        nullable=True,
        comment="ИНН"
    )

    contacts: Mapped[str] = mapped_column(
        sa.String(),
        nullable=False,
        server_default="",
        comment="Контактные данные (имена, телефоны, email)"
    )

    personal_account: Mapped[int] = mapped_column(
        sa.String(20),
        unique=True,
        nullable=False,
        comment="Лицевой счет"
    )

    date_add: Mapped[date] = mapped_column(
        sa.Date,
        nullable=False,
        server_default=sa.text("NOW()"),
        init=False,
        comment="Дата создания/добавления записи в БД"
    )

    # Тарифная политика
    tariff_policy_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.tariff_policy.id"),
        nullable=True,
        comment="Тарифная политика"
    )

    # Тарифная политика
    tariff_policy: Mapped["TariffPolicyOrm"] = relationship(
        back_populates="companies",
        lazy="noload"
    )

    min_balance: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        comment="Минимальный баланс (бесплатный овердрафт)"
    )

    overdraft_on: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.sql.false(),
        comment='Услуга "Овердрафт" подключена'
    )

    overdraft_sum: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        comment="Сумма овердрафта"
    )

    overdraft_days: Mapped[int] = mapped_column(
        sa.Integer(),
        nullable=False,
        server_default=sa.text("0"),
        comment="Срок овердрафта, дни"
    )

    overdraft_fee_percent: Mapped[float] = mapped_column(
        sa.Numeric(5, 3, asdecimal=False),
        nullable=False,
        server_default=sa.text("0.074"),
        comment="Комиссия за овердрафт, %"
    )

    # Список автомобилей этой организации
    cars: Mapped[List["CarOrm"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список пользователей, привязанных к этой организации
    users: Mapped[List["UserOrm"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список менеджеров ПроАВТО, привязанных к этой организации
    admin_company: Mapped[List["AdminCompanyOrm"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список карт этой организации
    cards: Mapped[List["CardOrm"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список балансов этой организации
    balances: Mapped[List["BalanceOrm"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False,
        order_by='desc(BalanceOrm.scheme)'
    )

    # Список уведомлений этой организации
    notification_mailings: Mapped[List["NotificationMailingOrm"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    repr_cols = ("name", "inn")
