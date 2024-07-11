import sqlalchemy as sa
from sqlalchemy import MetaData, inspect
from sqlalchemy.orm import MappedAsDataclass, DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncAttrs
from datetime import date, datetime
from typing import List, Dict, Any, Annotated

from fastapi_users.db import SQLAlchemyBaseUserTableUUID

from src.config import SCHEMA
from src.utils import enums

pk = Annotated[
    str,
    mapped_column(
        sa.Uuid(as_uuid=False),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
        init=False
    )
]


class Base(AsyncAttrs, MappedAsDataclass, DeclarativeBase):
    metadata = MetaData(schema=SCHEMA)

    id: Mapped[pk]

    repr_cols = tuple()

    def __repr__(self):
        # self.date_time.isoformat().replace('T', ' ')
        cols = []
        for idx, col in enumerate(self.__table__.columns.keys()):
            if col in self.repr_cols:
                cols.append(f"{col}={getattr(self, col)}")

        return f"<{self.__class__.__name__} {', '.join(cols)}>"

    def update_without_saving(self, data: Dict[str, Any]) -> None:
        for field, value in data.items():
            setattr(self, field, value)

    def dumps(self) -> Dict[str, Any]:
        # Формируем словарь, состоящий из полей модели
        dump = {column.key: getattr(self, column.key) for column in inspect(self).mapper.column_attrs}

        # Добавляем в словарь связанные модели
        relationships = inspect(self.__class__).relationships
        for rel in relationships:
            try:
                dump[rel.key] = getattr(self, rel.key)

            finally:
                pass

        return dump

    def annotate(self, data: Dict[str, Any]) -> Any:
        for field, value in data.items():
            setattr(self, field, value)
        return self


class Tariff(Base):
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
    transactions: Mapped[List["Transaction"]] = relationship(
        back_populates="tariff",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # История применения этого тарифа к организациям
    tariff_history: Mapped[List["TariffHistory"]] = relationship(
        back_populates="tariff",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    repr_cols = ("name",)


class Company(Base):
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
        sa.String(13),
        nullable=True,
        comment="ИНН"
    )

    contacts: Mapped[str] = mapped_column(
        sa.String(),
        nullable=False,
        server_default="",
        init=False,
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

    # Список автомобилей этой организации
    cars: Mapped[List["Car"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список пользователей, привязанных к этой организации
    users: Mapped[List["User"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список менеджеров ПроАВТО, привязанных к этой организации
    admin_company: Mapped[List["AdminCompany"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список карт этой организации
    cards: Mapped[List["Card"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список балансов этой организации
    balances: Mapped[List["Balance"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    repr_cols = ("name", "inn")


class Balance(Base):
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
    company: Mapped["Company"] = relationship(
        back_populates="balances",
        lazy="noload",
        init=False
    )

    scheme: Mapped[enums.ContractScheme] = mapped_column(
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

    """
    # Список договоров, привязанных к этому балансу
    card_bindings: Mapped[List["CardBinding"]] = relationship(
        back_populates="balance",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )
    """

    # Список карт, привязанных к этому балансу
    cards: Mapped[List["Card"]] = relationship(
        back_populates="balances",
        secondary="cargonomica.card_binding",
        lazy="noload",
        init=False
    )

    # Список поставщиков услуг, привязанных к этому балансу
    systems: Mapped[List["System"]] = relationship(
        back_populates="balances",
        secondary="cargonomica.card_binding",
        lazy="noload",
        init=False
    )

    # История тарифов этого баланса
    tariff_history: Mapped[List["TariffHistory"]] = relationship(
        back_populates="balance",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список транзакций, привязанных к этому балансу
    transactions: Mapped[List["Transaction"]] = relationship(
        back_populates="balance",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    repr_cols = ("balance", "scheme")


class TariffHistory(Base):
    __tablename__ = "tariff_history"
    __table_args__ = {
        'comment': (
            "Сведения из таблицы позволяют указать какой тариф применялся ранее и применяется сейчас "
            "при отражении операций с конкретным поставщиком услуг на соответствующем  балансе."
        )
    }

    # Тариф
    tariff_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.tariff.id"),
        comment="Тариф"
    )

    # Тариф
    tariff: Mapped["Tariff"] = relationship(
        back_populates="tariff_history",
        lazy="noload"
    )

    # Баланс
    balance_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.balance.id"),
        comment="Баланс"
    )

    # Баланс
    balance: Mapped["Balance"] = relationship(
        back_populates="tariff_history",
        lazy="noload"
    )

    # Поставщиик услуг
    system_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.system.id"),
        nullable=False,
        comment="Поставщиик услуг"
    )

    # Поставщиик услуг
    system: Mapped["System"] = relationship(
        back_populates="tariff_history",
        lazy="noload"
    )

    # Дата начала действия (тариф действует с 00:00:00 в указанную дату)
    start_date: Mapped[date] = mapped_column(
        sa.Date,
        nullable=False,
        comment="Дата начала действия (тариф действует с 00:00:00 в указанную дату)"
    )

    # Дата прекращения действия (тариф прекращает действовать с 00:00:00 в указанную дату)
    end_date: Mapped[date] = mapped_column(
        sa.Date,
        nullable=True,
        init=False,
        comment="Дата прекращения действия (тариф прекращает действовать с 00:00:00 в указанную дату)"
    )

    # Признак актуальности записи на текущий момент
    current: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.sql.true(),
        comment="Признак актуальности записи на текущий момент"
    )

    repr_cols = ("start_date", "end_date")


class Permition(Base):
    __tablename__ = "permition"
    __table_args__ = {
        'comment': 'Права доступа'
    }

    name: Mapped[str] = mapped_column(
        sa.String(50),
        unique=True,
        nullable=False,
        comment="Имя"
    )

    description: Mapped[str] = mapped_column(
        sa.String(),
        nullable=False,
        comment="Описание"
    )

    # Список ролей, содержащих это право
    role_permition: Mapped[List["RolePermition"]] = relationship(
        back_populates="permition",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    repr_cols = ("name",)


class Role(Base):
    __tablename__ = "role"
    __table_args__ = {
        'comment': 'Роли'
    }

    name: Mapped[str] = mapped_column(
        sa.String(50),
        unique=True,
        nullable=False,
        comment="Условное обозначение роли"
    )

    title: Mapped[str] = mapped_column(
        sa.String(50),
        unique=True,
        nullable=False,
        comment="Отображаемое наименование роли"
    )

    description: Mapped[str] = mapped_column(
        sa.String(),
        nullable=False,
        comment="Описание роли"
    )

    # Список пользователей с этой ролью
    users: Mapped[List["User"]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список прав для этой роли
    role_permition: Mapped[List["RolePermition"]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    repr_cols = ("title",)

    def has_permition(self, permition: enums.Permition) -> bool:
        if not self.role_permition:
            return False

        if permition in [rp.permition.name.upper() for rp in self.role_permition]:
            return True
        else:
            return False


class RolePermition(Base):
    __tablename__ = "role_permition"
    __table_args__ = (
        sa.UniqueConstraint("role_id", "permition_id"),
        {'comment': 'Привязка роей к правам доступа'}
    )

    role_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.role.id"),
        nullable=False,
        comment="Роль"
    )

    # Роль
    role: Mapped["Role"] = relationship(
        back_populates="role_permition",
        lazy="noload",
        init=False
    )

    permition_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.permition.id"),
        nullable=False,
        comment="Право"
    )

    # Право
    permition: Mapped["Permition"] = relationship(
        back_populates="role_permition",
        lazy="noload",
        init=False
    )

    repr_cols = ("role_id", "permition_id")


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "user"
    __table_args__ = {
        'comment': 'Пользователи'
    }

    id: Mapped[str] = mapped_column(
        sa.Uuid(as_uuid=False),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
        init=False
    )

    username: Mapped[str] = mapped_column(
        sa.String(50),
        unique=True,
        nullable=False,
        comment="Имя учетной записи (логин)"
    )

    hashed_password: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        comment="Хеш пароля"
    )

    first_name: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        comment="Имя"
    )

    last_name: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        comment="Фамилия"
    )

    email: Mapped[str] = mapped_column(
        sa.String(50),
        unique=True,
        comment="Email"
    )

    phone: Mapped[str] = mapped_column(
        sa.String(12),
        nullable=False,
        server_default='',
        comment="Телефон"
    )

    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.sql.false(),
        comment="Пользователь активен"
    )

    role_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.role.id"),
        nullable=False,
        comment="Роль"
    )

    # Роль
    role: Mapped["Role"] = relationship(
        back_populates="users",
        lazy="noload",
        init=False
    )

    company_id: Mapped[int] = mapped_column(
        sa.ForeignKey("cargonomica.company.id"),
        nullable=True,
        default=None,
        comment="Организация"
    )

    # Организация
    company: Mapped["Company"] = relationship(
        back_populates="users",
        lazy="noload",
        init=False
    )

    is_superuser: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.sql.false(),
        init=False,
        comment="Поле необходимо для связки с FastApiUsers"
    )

    is_verified: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.sql.false(),
        init=False,
        comment="Поле необходимо для связки с FastApiUsers"
    )

    # Список организации, привязанных к этому менеджеру ПроАВТО
    admin_company: Mapped[List["AdminCompany"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список автомобилей привязанных к этому пользователю
    # в случае, если он обладает ролью Водитель
    car_driver: Mapped[List["CarDriver"]] = relationship(
        back_populates="driver",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список карт, привязанных к этому пользователю
    cards: Mapped[List["Card"]] = relationship(
        back_populates="belongs_to_driver",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    repr_cols = ("username",)

    def is_admin_for_company(self, company_id: str) -> bool:
        return bool(list(filter(lambda ac: ac.company_id == company_id, self.admin_company)))

    def is_worker_of_company(self, company_id: str) -> bool:
        return self.company_id == company_id

    def company_ids_subquery(self) -> sa.Subquery:
        stmt = (
            sa.select(Company.id)
            .join(Company.admin_company)
            .where(AdminCompany.user_id == self.id)
            .subquery()
        )
        return stmt


class AdminCompany(Base):
    __tablename__ = "admin_company"
    __table_args__ = {
        'comment': 'Привязка пользователей с ролью <Менеджер ПроАВТО> к администрируемым организациям'
    }

    user_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.user.id"),
        nullable=False,
        init=True,
        comment="Пользователь"
    )

    # Пользователь
    user: Mapped["User"] = relationship(
        back_populates="admin_company",
        lazy="noload",
        init = False
    )

    company_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.company.id"),
        nullable = False,
        init = True,
        comment="Организация"
    )

    # Организация
    company: Mapped["Company"] = relationship(
        back_populates="admin_company",
        lazy="noload",
        init = False
    )

    repr_cols = ("user_id", "company_id")


class CardType(Base):
    __tablename__ = "card_type"
    __table_args__ = {
        'comment': 'Типы карт'
    }

    name: Mapped[str] = mapped_column(
        sa.String(50),
        unique=True,
        nullable=False,
        comment="Название типа"
    )

    # Список карт этого типа
    cards: Mapped[List["Card"]] = relationship(
        back_populates="card_type",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    repr_cols = ("name",)


class Car(Base):
    __tablename__ = "car"
    __table_args__ = {
        'comment': 'Автомобили'
    }

    master_db_id: Mapped[int] = mapped_column(
        sa.Integer(),
        nullable=True,
        init=False,
        comment="Идентификатор в боевой БД (для синхронизации)"
    )

    model: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        server_default="",
        comment="Марка/модель"
    )

    reg_number: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        comment="Государственный регистрационный номер"
    )

    company_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.company.id"),
        nullable=False,
        comment="Организация"
    )

    # Организация
    company: Mapped["Company"] = relationship(
        back_populates="cars",
        lazy="noload",
        init=False
    )

    # Список карт привязанных к этому автомобилю
    cards: Mapped[List["Card"]] = relationship(
        back_populates="belongs_to_car",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список водителей привязанных к этому автомобилю
    car_driver: Mapped[List["CarDriver"]] = relationship(
        back_populates="car",
        cascade="all, delete-orphan",
        init=False
    )

    repr_cols = ("model", "reg_number")


class CarDriver(Base):
    __tablename__ = "car_driver"
    __table_args__ = {
        'comment': 'Водители'
    }

    car_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.car.id"),
        nullable=False,
        comment="Автомобиль"
    )

    # Автомобиль
    car: Mapped["Car"] = relationship(
        back_populates="car_driver",
        lazy="noload"
    )

    driver_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.user.id"),
        nullable=False,
        comment="Водитель"
    )

    # Водитель
    driver: Mapped["User"] = relationship(
        back_populates="car_driver",
        lazy="noload"
    )

    repr_cols = ("car_id", "driver_id")


class Card(Base):
    __tablename__ = "card"
    __table_args__ = {
        'comment': 'Карты'
    }

    card_number: Mapped[str] = mapped_column(
        sa.String(20),
        unique=True,
        nullable=False,
        comment="Номер карты"
    )

    card_type_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.card_type.id"),
        comment="Тип карты"
    )

    # Тип карты
    card_type: Mapped["CardType"] = relationship(
        back_populates="cards",
        lazy="noload",
        init=False
    )

    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.sql.false(),
        comment="Карта активна"
    )

    # Организация
    company_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.company.id"),
        nullable=False,
        init=True,
        comment="Организация"
    )

    # Организация
    company: Mapped["Company"] = relationship(
        back_populates="cards",
        lazy="noload",
        init=False
    )

    belongs_to_car_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.car.id"),
        nullable=True,
        comment="Автомобиль, с которым ассоциирована карта"
    )

    # Автомобиль, с которым ассоциирована карта
    belongs_to_car: Mapped["Car"] = relationship(
        back_populates="cards",
        lazy="noload",
        init=False
    )

    belongs_to_driver_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.user.id"),
        nullable=True,
        comment="Водитель, с которым ассоциирована карта"
    )

    # Водитель, с которым ассоциирована карта
    belongs_to_driver: Mapped["User"] = relationship(
        back_populates="cards",
        lazy="noload",
        init=False
    )

    date_last_use: Mapped[date] = mapped_column(
        sa.Date,
        nullable=True,
        init=False,
        comment="Дата последнего использования"
    )

    manual_lock: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.sql.false(),
        init=False,
        comment="Признак ручной блокировки"
    )

    """
    # Список связей этой карты
    card_bindings: Mapped[List["CardBinding"]] = relationship(
        back_populates="card",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )
    """
    # Список балансов, связанных с этой картой
    balances: Mapped[List["Balance"]] = relationship(
        back_populates="cards",
        secondary="cargonomica.card_binding",
        lazy="noload",
        init=False
    )

    # Список систем, связанных с этой картой
    systems: Mapped[List["System"]] = relationship(
        back_populates="cards",
        secondary="cargonomica.card_binding",
        lazy="noload",
        init=False
    )

    # Список транзакций, привязанных к этой карте
    transactions: Mapped[List["Transaction"]] = relationship(
        back_populates="card",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    repr_cols = ("card_number",)


class System(Base):
    __tablename__ = "system"
    __table_args__ = {
        'comment': 'Поставщики услуг'
    }

    master_db_id: Mapped[int] = mapped_column(
        sa.Integer(),
        nullable=True,
        init=False,
        comment="Идентификатор в боевой БД (для синхронизации)"
    )

    full_name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        unique=True,
        comment="Полное наименование организации"
    )

    short_name: Mapped[str] = mapped_column(
        sa.String(30),
        nullable=False,
        unique=True,
        comment="Сокращенное наименование организации"
    )

    balance: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False,
        comment="Наш текущий баланс в системе поспавщика услуг (актуален для перекупной схемы)"
    )

    transaction_days: Mapped[int] = mapped_column(
        sa.SmallInteger(),
        nullable=False,
        server_default=sa.text("50"),
        comment="Период, за который запрашиваются транзакции при синхронизации"
    )

    agency_scheme_enabled: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.sql.false(),
        comment="Возможность применения агентской схемы работы с поставщиком услуг"
    )

    overbought_scheme_enabled: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.sql.false(),
        comment="Возможность применения перекупной схемы работы с поставщиком услуг"
    )

    transactions_sync_dt: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=True,
        init=False,
        comment="Дата последней успешной синхронизаци транзакций"
    )

    cards_sync_dt: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=True,
        init=False,
        comment="Дата последней успешной синхронизации карт"
    )

    balance_sync_dt: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=True,
        init=False,
        comment="Дата последней успешной синхронизации баланса"
    )

    """
    # Список договоров, привязанных к этой системе
    card_bindings: Mapped[List["CardBinding"]] = relationship(
        back_populates="system",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )
    """
    # Список балансов, связанных с этой системой
    balances: Mapped[List["Balance"]] = relationship(
        back_populates="systems",
        secondary="cargonomica.card_binding",
        lazy="noload",
        init=False
    )

    # Список карт, связанных с этой системой
    cards: Mapped[List["Card"]] = relationship(
        back_populates="systems",
        secondary="cargonomica.card_binding",
        lazy="noload",
        init=False
    )

    # Список договоров, привязанных к этой системе
    tariff_history: Mapped[List["TariffHistory"]] = relationship(
        back_populates="system",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список транзакций, привязанных к этому поставщику услуг
    transactions: Mapped[List["Transaction"]] = relationship(
        back_populates="system",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список товаров и услуг, привязанных к этому поставщику услуг
    outer_goods: Mapped[List["OuterGoods"]] = relationship(
        back_populates="system",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    repr_cols = ("full_name",)


class CardBinding(Base):
    __tablename__ = "card_binding"
    __table_args__ = {
        'comment': (
            "Сведения из таблицы позволяют указать к какому поставщику услуг привязана карта и какому клиенту "
            "она в данный момент принадлежит (привязка через баланс)."
        )
    }

    # Карта
    card_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.card.id"),
        nullable=False,
        comment="Карта"
    )

    """
    # Карта
    card: Mapped["Card"] = relationship(
        back_populates="card_bindings",
        lazy="noload"
    )
    """

    # Поставщиик услуг
    system_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.system.id"),
        nullable=False,
        comment="Поставщиик услуг"
    )

    """
    # Поставщиик услуг
    system: Mapped["System"] = relationship(
        back_populates="card_bindings",
        lazy="noload"
    )
    """

    # Баланс
    balance_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.balance.id"),
        nullable=True,
        init=False,
        comment="Баланс"
    )

    """
    # Баланс
    balance: Mapped["Balance"] = relationship(
        back_populates="card_bindings",
        lazy="noload",
        init=False
    )
    """

    repr_cols = ("card_id",)


class InnerGoods(Base):
    __tablename__ = "inner_goods"
    __table_args__ = {
        'comment': 'Товары/услуги в нашей системе'
    }

    name: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        unique=True,
        comment="Наименование в нашей системе"
    )

    # Список внешних товаров и услуг, привязанных к этой номенклатуре внутренних товаров/услуг
    outer_goods: Mapped[List["OuterGoods"]] = relationship(
        back_populates="inner_goods",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    repr_cols = ("name",)


class OuterGoods(Base):
    __tablename__ = "outer_goods"
    __table_args__ = (
        sa.UniqueConstraint("name", "system_id"),
        {'comment': 'Товары/услуги в системе поставщика услуг'}
    )

    name: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        comment="Наименование в системе поставщика услуг"
    )

    system_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.system.id"),
        nullable=False,
        comment="Система"
    )

    # Система
    system: Mapped["System"] = relationship(
        back_populates="outer_goods",
        lazy="noload"
    )

    inner_goods_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.inner_goods.id"),
        nullable=True,
        init=False,
        comment="Внутренняя номенклатура товара/услуги"
    )

    # Внутренняя номенклатура товаров/услуг, с которой ассоциирована данная номенклатура
    # внешних товаров/услуг
    inner_goods: Mapped["InnerGoods"] = relationship(
        back_populates="outer_goods",
        lazy="noload",
        init=False
    )

    # Список транзакций, привязанных к этому товару / этой услуге
    transactions: Mapped[List["Transaction"]] = relationship(
        back_populates="outer_goods",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    repr_cols = ("name",)


class Transaction(Base):
    __tablename__ = "transaction"
    __table_args__ = {
        'comment': 'Транзакции'
    }

    master_db_id: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        server_default="",
        init=False,
        comment="Идентификатор в боевой БД (для синхронизации)"
    )

    external_id: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        server_default="",
        init=False,
        comment="Внешний идентификатор (идентификатор в системе поставщика услуг)"
    )

    date_time: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=False,
        server_default=sa.text("NOW()"),
        comment="Время совершения транзакции"
    )

    date_time_load: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=False,
        server_default=sa.text("NOW()"),
        init=False,
        comment="Время прогрузки в БД"
    )

    is_debit: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        comment="Направление транзакции: покупка или возврат"
    )

    # Карта
    card_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.card.id"),
        nullable=True,
        comment="Карта"
    )

    # Карта
    card: Mapped["Card"] = relationship(
        back_populates="transactions",
        lazy="noload"
    )

    # Баланс
    balance_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.balance.id"),
        nullable=True,
        comment="Карта"
    )

    # Баланс
    balance: Mapped["Balance"] = relationship(
        back_populates="transactions",
        lazy="noload"
    )

    # Поставщик услуг
    system_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.system.id"),
        nullable=True,
        comment="Поставщик услуг"
    )

    # Баланс
    system: Mapped["System"] = relationship(
        back_populates="transactions",
        lazy="noload"
    )

    azs_code: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        server_default="",
        init=False,
        comment="Код АЗС"
    )

    azs_address: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        server_default="",
        init=False,
        comment="Адрес АЗС"
    )

    outer_goods_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.outer_goods.id"),
        nullable=True,
        comment="Товар/услуга"
    )

    # Товар/услуга
    outer_goods: Mapped["OuterGoods"] = relationship(
        back_populates="transactions",
        lazy="noload"
    )

    fuel_volume: Mapped[float] = mapped_column(
        sa.Float(),
        nullable=False,
        server_default=sa.text("0"),
        init=False,
        comment="Литры"
    )

    price: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False,
        comment="Цена"
    )

    transaction_sum: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False,
        comment="Сумма по транзакции"
    )

    discount_sum: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False,
        comment="Скидка"
    )

    tariff_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.tariff.id"),
        nullable=True,
        comment="Тариф"
    )

    # Тариф
    tariff: Mapped["Tariff"] = relationship(
        back_populates="transactions",
        lazy="noload"
    )

    fee_percent: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False,
        comment="Сумма комиссионного вознаграждения по тарифу"
    )

    fee_sum: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False,
        comment="Сумма комиссионного вознаграждения по тарифу"
    )

    total_sum: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False,
        comment="Итоговая сумма для применения к балансу организации"
    )

    card_balance: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False,
        comment="Баланс карты после выполнения транзакции"
    )

    company_balance: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False,
        comment="Баланс организации после выполнения транзакции"
    )

    comments: Mapped[str] = mapped_column(
        sa.String(),
        nullable=False,
        server_default="",
        comment="Комментарии"
    )

    repr_cols = ("id", "transaction_sum", "date_time")


class LogType(Base):
    __tablename__ = "log_type"
    __table_args__ = {
        'comment': 'Типы логов'
    }

    name: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        unique=True,
        comment="Название типа"
    )

    # Список логов этого типа
    logs: Mapped[List["Log"]] = relationship(
        back_populates="log_type",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    repr_cols = ("name",)


class Log(Base):
    __tablename__ = "log"
    __table_args__ = {
        'comment': 'Логирование'
    }

    date_time: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=False,
        server_default=sa.text("NOW()"),
        init=False,
        comment="Время"
    )

    log_type_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.log_type.id"),
        nullable=False,
        comment="Тип лога"
    )

    # Тип лога
    log_type: Mapped["LogType"] = relationship(
        back_populates="logs",
        lazy="noload",
        init=False
    )

    message: Mapped[str] = mapped_column(
        sa.String(),
        nullable=False,
        comment="Сообщение"
    )

    details: Mapped[str] = mapped_column(
        sa.String(),
        nullable=False,
        server_default='',
        init=False,
        comment="Подробности"
    )

    username: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        server_default='',
        init=False,
        comment="Имя пользователя"
    )

    previous_state: Mapped[str] = mapped_column(
        sa.String(),
        nullable=False,
        server_default='',
        init=False,
        comment="Предыдущее состояние"
    )

    new_state: Mapped[str] = mapped_column(
        sa.String(),
        nullable=False,
        server_default='',
        init=False,
        comment="Новое состояние"
    )

    repr_cols = ("message",)
