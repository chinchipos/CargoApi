from datetime import date
from typing import List

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.balance import BalanceOrm
from src.database.models.base import Base
from src.database.models.goods_category import GoodsCategory
from src.utils.enums import ContractScheme


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

    contract_number: Mapped[int] = mapped_column(
        sa.String(150),
        unique=False,
        nullable=False,
        comment="Номер договора"
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
        init=True,
        comment="Тарифная политика"
    )

    # Тарифная политика
    tariff_policy: Mapped["TariffPolicyOrm"] = relationship(
        back_populates="companies",
        init=False,
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

    # История владения картами
    card_history: Mapped[List["CardHistoryOrm"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # История применения траифных политик
    tariff_policy_history: Mapped[List["TariffPolicyHistoryOrm"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список карточных групп этой организации
    card_groups: Mapped[List["CardGroupOrm"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список групповых лимитов этой организации
    group_limits: Mapped[List["GroupLimitOrm"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    def overbought_balance(self) -> BalanceOrm | None:
        for balance in self.balances:
            if balance.scheme == ContractScheme.OVERBOUGHT:
                return balance

    def has_card_group(self, system_short_name: str) -> bool:
        for group in self.card_groups:
            if group.system.short_name == system_short_name:
                return True
        return False

    def get_card_group(self, system_short_name: str):
        for group in self.card_groups:
            if group.system.short_name == system_short_name:
                return group

    def has_card_limit_with_certain_category(self, system_id: str, inner_goods_category: GoodsCategory) -> bool:
        for card in self.cards:
            for limit in card.limits:
                if limit.system_id == system_id and limit.inner_goods_category == inner_goods_category:
                    return True
        return False

    repr_cols = ("name", "inn")
