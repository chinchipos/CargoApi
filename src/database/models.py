import sqlalchemy as sa
from sqlalchemy import MetaData
from sqlalchemy.orm import (
    MappedAsDataclass,
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from datetime import date, datetime
from typing import List

from fastapi_users.db import SQLAlchemyBaseUserTableUUID

from src.utils import enums


class Base(AsyncAttrs, MappedAsDataclass, DeclarativeBase):
    metadata = MetaData(schema="cargonomica")


class Author(Base):
    __tablename__ = "author"

    id: Mapped[str] = mapped_column(
        sa.Uuid(as_uuid = False),
        primary_key = True,
        server_default = sa.text("uuid_generate_v4()"),
        init=False
    )

    first_name: Mapped[str] = mapped_column(
        sa.String(50),
        nullable = False
    )

    last_name: Mapped[str] = mapped_column(
        sa.String(50),
        nullable = False
    )

    date_birth: Mapped[date] = mapped_column(
        sa.Date,
        nullable = False
    )

    biography: Mapped[str] = mapped_column(
        sa.String(),
        nullable = False,
        server_default = ""
    )

    books: Mapped[List["Book"]] = relationship(
        back_populates="author",
        cascade="all, delete-orphan",
        init=False
    )

    def __repr__(self) -> str:
        return f"Author({self.first_name} {self.last_name})"


class Book(Base):
    __tablename__ = "book"

    id: Mapped[str] = mapped_column(
        sa.Uuid(as_uuid = False),
        primary_key = True,
        server_default = sa.text("uuid_generate_v4()"),
        init=False
    )

    title: Mapped[str] = mapped_column(
        sa.String(50),
        nullable = False
    )

    annotation: Mapped[str] = mapped_column(
        sa.String(50),
        nullable = False
    )

    date_publishing: Mapped[date] = mapped_column(
        sa.Date,
        nullable = False,
        server_default = sa.text("NOW()")
    )

    author_id: Mapped[int] = mapped_column(
        sa.ForeignKey("cargonomica.author.id"),
        nullable = True
    )

    author: Mapped["Author"] = relationship(
        back_populates = "books",
        lazy = "noload",
        init=False
    )

    def __repr__(self) -> str:
        return f"Book({self.title})"


class Tariff(Base):
    __tablename__ = "tariff"

    id: Mapped[str] = mapped_column(
        sa.Uuid(as_uuid=False),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
        init=False
    )

    # Идентификатор в боевой БД (для синхронизации)
    master_db_id: Mapped[int] = mapped_column(
        sa.Integer(),
        init=False
    )

    # Название
    name: Mapped[str] = mapped_column(
        sa.String(50),
        unique=True,
        nullable=False
    )

    # Комиссия, %
    fee_percent: Mapped[float] = mapped_column(
        sa.Numeric(5, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False
    )

    # Список компаний на этом тарифе
    companies: Mapped[List["Company"]] = relationship(
        back_populates="tariff",
        cascade="all, delete-orphan",
        init=False
    )

    # Список транзакций по этому тарифу
    transactions: Mapped[List["Transaction"]] = relationship(
        back_populates="tariff",
        cascade="all, delete-orphan",
        init=False
    )

    # История применения этого тарифа к организациям
    tariff_history: Mapped[List["TariffHistory"]] = relationship(
        back_populates="tariff",
        cascade="all, delete-orphan",
        init=False
    )

    def __repr__(self) -> str:
        return f"Tariff({self.name})"


class Company(Base):
    __tablename__ = "company"

    id: Mapped[str] = mapped_column(
        sa.Uuid(as_uuid=False),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
        init=False
    )

    # Идентификатор в боевой БД (для синхронизации)
    master_db_id: Mapped[int] = mapped_column(
        sa.Integer(),
        init=False
    )

    # Наименование организации
    name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False
    )

    # ИНН
    inn: Mapped[str] = mapped_column(
        sa.String(13),
        unique=True,
        nullable=False
    )

    # Адрес
    address: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        server_default="",
        init=False
    )

    # Контактные данные (имена, телефоны, email)
    contacts: Mapped[str] = mapped_column(
        sa.String(),
        nullable=False,
        server_default="",
        init=False
    )

    # Лицевой счет
    personal_account: Mapped[int] = mapped_column(
        sa.String(20),
        unique=True,
        nullable=False
    )

    # Дата создания/добавления записи в БД
    date_add: Mapped[date] = mapped_column(
        sa.Date,
        nullable=False,
        server_default=sa.text("NOW()"),
        init=False
    )

    # Текущий баланс
    current_balance: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False
    )

    # Минимальный баланс
    min_balance: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False
    )

    # Минимальный баланс на период
    min_balance_on_period: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False
    )

    # Дата прекращения действия мин. баланса на период
    min_balance_period_end_date: Mapped[date] = mapped_column(
        sa.Date,
        nullable=True,
        init=False
    )

    # Тариф
    tariff_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.tariff.id"),
        nullable=True,
        init=False
    )

    # Тариф
    tariff: Mapped["Tariff"] = relationship(
        back_populates="companies",
        lazy="noload",
        init=False
    )

    # Список автомобилей этой организации
    cars: Mapped[List["Car"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        init=False
    )

    # Список карт привязанных к этой организации
    cards: Mapped[List["Card"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        init=False
    )

    # Список транзакций привязанных к этой организации
    transactions: Mapped[List["Transaction"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        init=False
    )

    # Список пользователей, привязанных к этой организации
    users: Mapped[List["User"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        init=False
    )

    # Список менеджеров ПроАВТО, привязанных к этой организации
    admin_company: Mapped[List["AdminCompany"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        init=False
    )

    # История тарифов этой организации
    tariff_history: Mapped[List["TariffHistory"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        init=False
    )

    def __repr__(self) -> str:
        return f"Company(Наименование: {self.name}, ИНН: {self.inn})"


class TariffHistory(Base):
    __tablename__ = "tariff_history"

    id: Mapped[str] = mapped_column(
        sa.Uuid(as_uuid=False),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
        init=False
    )

    # Организация
    company_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.company.id")
    )

    # Организация
    company: Mapped["Company"] = relationship(
        back_populates="tariff_history",
        lazy="noload"
    )

    # Тариф
    tariff_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.tariff.id")
    )

    # Тариф
    tariff: Mapped["Tariff"] = relationship(
        back_populates="tariff_history",
        lazy="noload"
    )

    # Дата начала действия (тариф действует с 00:00:00 в указанную дату)
    start_date: Mapped[date] = mapped_column(
        sa.Date,
        nullable=False
    )

    # Дата прекращения действия (тариф прекращает действовать с 00:00:00 в указанную дату)
    end_date: Mapped[date] = mapped_column(
        sa.Date,
        init=False
    )

    def __repr__(self) -> str:
        return "TariffHistory(с {} по {})".format(
            self.start_date.isoformat(),
            self.end_date.isoformat() if self.end_date else 'настоящее время'
        )


class Permition(Base):
    __tablename__ = "permition"

    id: Mapped[str] = mapped_column(
        sa.Uuid(as_uuid=False),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
        init=False
    )

    # Имя
    name: Mapped[str] = mapped_column(
        sa.String(50),
        unique=True,
        nullable=False
    )

    # Описание
    description: Mapped[str] = mapped_column(
        sa.String(),
        nullable=False
    )

    # Список ролей, содержащих это право
    role_permition: Mapped[List["RolePermition"]] = relationship(
        back_populates="permition",
        cascade="all, delete-orphan",
        init=False
    )

    def __repr__(self) -> str:
        return f"Permition({self.name})"


class Role(Base):
    __tablename__ = "role"

    id: Mapped[str] = mapped_column(
        sa.Uuid(as_uuid=False),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
        init=False
    )

    # Условное обозначение роли
    name: Mapped[str] = mapped_column(
        sa.String(50),
        unique=True,
        nullable=False
    )

    # Отображаемое наименование роли
    title: Mapped[str] = mapped_column(
        sa.String(50),
        unique=True,
        nullable=False
    )

    # Описание роли
    description: Mapped[str] = mapped_column(
        sa.String(),
        nullable=False
    )

    # Список пользователей с этой ролью
    users: Mapped[List["User"]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
        init=False
    )

    # Список прав для этой роли
    role_permition: Mapped[List["RolePermition"]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
        init=False
    )

    def __repr__(self) -> str:
        return f"Role({self.title})"

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
    )

    id: Mapped[str] = mapped_column(
        sa.Uuid(as_uuid=False),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
        init=False
    )

    # Роль
    role_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.role.id"),
        nullable=False
    )

    # Роль
    role: Mapped["Role"] = relationship(
        back_populates="role_permition",
        lazy="noload",
        init=False
    )

    # Право
    permition_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.permition.id"),
        nullable=False
    )

    # Право
    permition: Mapped["Permition"] = relationship(
        back_populates="role_permition",
        lazy="noload",
        init=False
    )

    def __repr__(self) -> str:
        return f"RolePermition(role_id: {self.role_id}, permition_id: {self.permition_id})"


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "user"

    id: Mapped[str] = mapped_column(
        sa.Uuid(as_uuid=False),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
        init=False
    )

    # Имя учетной записи (логин)
    username: Mapped[str] = mapped_column(
        sa.String(50),
        unique=True,
        nullable=False
    )

    # Хеш пароля
    hashed_password: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False
    )

    # Имя
    first_name: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False
    )

    # Фамилия
    last_name: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False
    )

    # Email
    email: Mapped[str] = mapped_column(
        sa.String(50),
        unique=True
    )

    # Телефон
    phone: Mapped[str] = mapped_column(
        sa.String(12),
        nullable=False,
        server_default=''
    )

    # Пользователь активен
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.sql.false(),
        init=False
    )

    # Роль
    role_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.role.id"),
        nullable=False
    )

    # Роль
    role: Mapped["Role"] = relationship(
        back_populates="users",
        lazy="noload",
        init=False
    )

    # Организация
    company_id: Mapped[int] = mapped_column(
        sa.ForeignKey("cargonomica.company.id"),
        nullable=True,
        init=False
    )

    # Организация
    company: Mapped["Company"] = relationship(
        back_populates="users",
        lazy="noload",
        init=False
    )

    # Поле необходимо для связки с FastApiUsers
    is_superuser: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.sql.false(),
        init=False
    )

    # Поле необходимо для связки с FastApiUsers
    is_verified: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.sql.false(),
        init=False
    )

    # Список организации, привязанных к этому менеджеру ПроАВТО
    admin_company: Mapped[List["AdminCompany"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        init=False
    )

    # Список автомобилей привязанных к этому пользователю
    # в случае, если он обладает ролью Водитель
    car_driver: Mapped[List["CarDriver"]] = relationship(
        back_populates="driver",
        cascade="all, delete-orphan",
        init=False
    )

    # Список карт, привязанных к этому пользователю
    cards: Mapped[List["Card"]] = relationship(
        back_populates="belongs_to_driver",
        cascade="all, delete-orphan",
        init=False
    )

    def __repr__(self) -> str:
        return f"User({self.username})"


class AdminCompany(Base):
    __tablename__ = "admin_company"

    id: Mapped[str] = mapped_column(
        sa.Uuid(as_uuid=False),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
        init=False
    )

    # Пользователь
    user_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.user.id"),
        nullable=False,
        init=False
    )

    # Пользователь
    user: Mapped["User"] = relationship(
        back_populates="admin_company",
        lazy="noload"
    )

    # Организация
    company_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.company.id")
    )

    # Организация
    company: Mapped["Company"] = relationship(
        back_populates="admin_company",
        lazy="noload"
    )

    def __repr__(self) -> str:
        return f"AdminCompany(Admin: {self.user_id}, Company: {self.company_id})"


class CardType(Base):
    __tablename__ = "card_type"

    id: Mapped[str] = mapped_column(
        sa.Uuid(as_uuid=False),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
        init=False
    )

    # Название типа
    name: Mapped[str] = mapped_column(
        sa.String(50),
        unique=True,
        nullable=False
    )

    # Список карт этого типа
    cards: Mapped[List["Card"]] = relationship(
        back_populates="card_type",
        cascade="all, delete-orphan",
        init=False
    )

    def __repr__(self) -> str:
        return f"CardType({self.name})"


class Car(Base):
    __tablename__ = "car"

    id: Mapped[str] = mapped_column(
        sa.Uuid(as_uuid=False),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
        init=False
    )

    # Идентификатор в боевой БД (для синхронизации)
    master_db_id: Mapped[int] = mapped_column(
        sa.Integer(),
        init=False
    )

    # Марка/модель
    model: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        server_default="",
        init=False
    )

    # Государственный регистрационный номер
    reg_number: Mapped[str] = mapped_column(
        sa.String(20),
        unique=True,
        nullable=False
    )

    # Организация
    company_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.company.id"),
        nullable=False,
        init=False
    )

    # Организация
    company: Mapped["Company"] = relationship(
        back_populates="cars",
        lazy="noload"
    )

    # Список карт привязанных к этому автомобилю
    cards: Mapped[List["Card"]] = relationship(
        back_populates="belongs_to_car",
        cascade="all, delete-orphan",
        init=False
    )

    # Список водителей привязанных к этому автомобилю
    car_driver: Mapped[List["CarDriver"]] = relationship(
        back_populates="car",
        cascade="all, delete-orphan",
        init=False
    )

    def __repr__(self) -> str:
        return f"Car({self.model} {self.reg_number})"


class CarDriver(Base):
    __tablename__ = "car_driver"

    id: Mapped[str] = mapped_column(
        sa.Uuid(as_uuid=False),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
        init=False
    )

    # Автомобиль
    car_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.car.id"),
        nullable=False
    )

    # Автомобиль
    car: Mapped["Car"] = relationship(
        back_populates="car_driver",
        lazy="noload"
    )

    # Водитель
    driver_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.user.id"),
        nullable=False
    )

    # Водитель
    driver: Mapped["User"] = relationship(
        back_populates="car_driver",
        lazy="noload"
    )

    def __repr__(self) -> str:
        return f"CarDriver(Карта: {self.car_id}, Система: {self.driver_id})"


class Card(Base):
    __tablename__ = "card"

    id: Mapped[str] = mapped_column(
        sa.Uuid(as_uuid=False),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
        init=False
    )

    # Номер карты
    card_number: Mapped[str] = mapped_column(
        sa.String(20),
        unique=True,
        nullable=False
    )

    # Тип карты
    card_type_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.card_type.id")
    )

    # Тип карты
    card_type: Mapped["CardType"] = relationship(
        back_populates="cards",
        lazy="noload"
    )

    # Карта активна
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.sql.false(),
        init=False
    )

    # Организация, с которой ассоциирована карта
    company_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.company.id"),
        nullable=True,
        init=False
    )

    # Организация, с которой ассоциирована карта
    company: Mapped["Company"] = relationship(
        back_populates="cards",
        lazy="noload"
    )

    # Автомобиль, с которым ассоциирована карта
    belongs_to_car_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.car.id"),
        nullable=True,
        init=False
    )

    # Автомобиль, с которым ассоциирована карта
    belongs_to_car: Mapped["Car"] = relationship(
        back_populates="cards",
        lazy="noload"
    )

    # Водитель, с которым ассоциирована карта
    belongs_to_driver_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.user.id"),
        nullable=True,
        init=False
    )

    # Водитель, с которым ассоциирована карта
    belongs_to_driver: Mapped["User"] = relationship(
        back_populates="cards",
        lazy="noload"
    )

    # Дата последнего использования
    date_last_use: Mapped[date] = mapped_column(
        sa.Date,
        nullable=True,
        init=False
    )

    # Признак ручной блокировки
    manual_lock: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.sql.false(),
        init=False
    )

    # Список систем, к которым привязана эта карта
    card_system: Mapped[List["CardSystem"]] = relationship(
        back_populates="card",
        cascade="all, delete-orphan",
        init=False
    )

    # Список транзакций, привязанных к этой карте
    transactions: Mapped[List["Transaction"]] = relationship(
        back_populates="card",
        cascade="all, delete-orphan",
        init=False
    )

    def __repr__(self) -> str:
        return f"Card(Номер: {self.card_number})"


class System(Base):
    __tablename__ = "system"

    id: Mapped[str] = mapped_column(
        sa.Uuid(as_uuid=False),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
        init=False
    )

    # Идентификатор в боевой БД (для синхронизации)
    master_db_id: Mapped[int] = mapped_column(
        sa.Integer(),
        init=False
    )

    # Полное наименование организации
    full_name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        unique=True
    )

    # Сокращенное наименование организации
    short_name: Mapped[str] = mapped_column(
        sa.String(30),
        nullable=False,
        unique=True
    )

    # Логин
    login: Mapped[str] = mapped_column(
        sa.String(50),
        server_default='',
        init=False
    )

    # Пароль
    password: Mapped[str] = mapped_column(
        sa.String(255),
        server_default='',
        init=False
    )

    # Номер договора
    contract_num: Mapped[str] = mapped_column(
        sa.String(50),
        server_default='',
        init=False
    )

    # Текущий баланс
    balance: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False
    )

    # Период, за который запрашиваются транзакции при синхронизации
    transaction_days: Mapped[int] = mapped_column(
        sa.SmallInteger(),
        nullable=False,
        server_default=sa.text("50"),
        init=False
    )

    # Дата последнего успешного сеанса загрузки транзакций
    transactions_sync_dt: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=True,
        init=False
    )

    # Дата последнего успешного сеанса загрузки карт
    cards_sync_dt: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=True,
        init=False
    )

    # Дата последнего успешного сеанса загрузки баланса
    balance_sync_dt: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=True,
        init=False
    )

    # Список карт, привязанных к этой системе
    card_system: Mapped[List["CardSystem"]] = relationship(
        back_populates="system",
        cascade="all, delete-orphan",
        init=False
    )

    # Список товаров и услуг, привязанных к этой системе
    outer_goods: Mapped[List["OuterGoods"]] = relationship(
        back_populates="system",
        cascade="all, delete-orphan",
        init=False
    )

    # Список транзакций, привязанных к этой системе
    transactions: Mapped[List["Transaction"]] = relationship(
        back_populates="system",
        cascade="all, delete-orphan",
        init=False
    )

    def __repr__(self) -> str:
        return f"System({self.full_name})"


class CardSystem(Base):
    __tablename__ = "card_system"

    id: Mapped[str] = mapped_column(
        sa.Uuid(as_uuid=False),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
        init=False
    )

    # Карта
    card_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.card.id"),
        nullable=False
    )

    # Карта
    card: Mapped["Card"] = relationship(
        back_populates="card_system",
        lazy="noload"
    )

    # Система
    system_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.system.id"),
        nullable=False
    )

    # Система
    system: Mapped["System"] = relationship(
        back_populates="card_system",
        lazy="noload"
    )

    def __repr__(self) -> str:
        return f"CardSystem(Карта: {self.card_id}, Система: {self.system_id})"


class InnerGoods(Base):
    __tablename__ = "inner_goods"

    id: Mapped[str] = mapped_column(
        sa.Uuid(as_uuid=False),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
        init=False
    )

    # Наименование
    name: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        unique=True
    )

    # Список внешних товаров и услуг, привязанных к этой номенклатуре внутренних товаров/услуг
    outer_goods: Mapped[List["OuterGoods"]] = relationship(
        back_populates="inner_goods",
        cascade="all, delete-orphan",
        init=False
    )

    def __repr__(self) -> str:
        return f"InnerGoods({self.name})"


class OuterGoods(Base):
    __tablename__ = "outer_goods"

    id: Mapped[str] = mapped_column(
        sa.Uuid(as_uuid=False),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
        init=False
    )

    # Наименование
    name: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False
    )

    # Система
    system_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.system.id"),
        nullable=False
    )

    # Система
    system: Mapped["System"] = relationship(
        back_populates="outer_goods",
        lazy="noload"
    )

    # Внутренняя номенклатура товаров/услуг, с которой ассоциирована данная номенклатура
    # внешних товаров/услуг
    inner_goods_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.inner_goods.id"),
        init=False
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
        init=False
    )

    def __repr__(self) -> str:
        return f"OuterGoods({self.name})"


class Transaction(Base):
    __tablename__ = "transaction"

    id: Mapped[str] = mapped_column(
        sa.Uuid(as_uuid=False),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
        init=False
    )

    # Идентификатор в боевой БД (для синхронизации)
    master_db_id: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        server_default="",
        init=False
    )

    # Внешний идентификатор (идентификатор в системе поставщика услуг)
    external_id: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        server_default="",
        init=False
    )

    # Время транзакции
    date_time: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=False,
        server_default=sa.text("NOW()")
    )

    # Время прогрузки в БД
    date_time_load: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=False,
        server_default=sa.text("NOW()"),
        init=False
    )

    # Направление транзакции: покупка или возврат
    debit: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False
    )

    # Система
    system_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.system.id"),
        nullable=True,
    )

    # Система
    system: Mapped["System"] = relationship(
        back_populates="transactions",
        lazy="noload"
    )

    # Карта
    card_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.card.id"),
        nullable=True,
    )

    # Карта
    card: Mapped["Card"] = relationship(
        back_populates="transactions",
        lazy="noload"
    )

    # Организация
    company_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.company.id"),
        nullable=True  # Возможна ситуация когда карта не присвоена клиенту, но ей уже пользуются
    )

    # Организация
    company: Mapped["Company"] = relationship(
        back_populates="transactions",
        lazy="noload"
    )

    # АЗС
    azs_code: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        server_default="",
        init=False
    )

    azs_address: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        server_default="",
        init=False
    )

    # Товар/услуга
    outer_goods_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.outer_goods.id"),
        nullable=True,
    )

    # Товар/услуга
    outer_goods: Mapped["OuterGoods"] = relationship(
        back_populates="transactions",
        lazy="noload"
    )

    # Литры
    fuel_volume: Mapped[float] = mapped_column(
        sa.Float(),
        nullable=False,
        server_default=sa.text("0"),
        init=False
    )

    # Цена
    price: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False
    )

    # Сумма по транзакции
    transaction_sum: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False
    )

    # Скидка
    discount_sum: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False
    )

    # Тариф
    tariff_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.tariff.id"),
        nullable=True,
    )

    # Тариф
    tariff: Mapped["Tariff"] = relationship(
        back_populates="transactions",
        lazy="noload"
    )

    # Сумма комиссионного вознаграждения по тарифу
    fee_percent: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False
    )

    # Сумма комиссионного вознаграждения по тарифу
    fee_sum: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False
    )

    # Итоговая сумма для применения к балансу организации
    total_sum: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False
    )

    # Баланс карты после выполнения транзакции
    card_balance_after: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False
    )

    # Баланс организации после выполнения транзакции
    company_balance_after: Mapped[float] = mapped_column(
        sa.Numeric(12, 2, asdecimal=False),
        nullable=False,
        server_default=sa.text("0"),
        init=False
    )

    # Комментарии
    comments: Mapped[str] = mapped_column(
        sa.String(),
        nullable=False,
        server_default=""
    )

    def __repr__(self) -> str:
        return "Transaction(ID: {}, Сумма: {} руб, Время: {})".format(
            self.id,
            self.transaction_sum,
            self.date_time.isoformat().replace('T', ' ')
        )


class LogType(Base):
    __tablename__ = "log_type"

    id: Mapped[str] = mapped_column(
        sa.Uuid(as_uuid=False),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
        init=False
    )

    # Название типа
    name: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        unique=True
    )

    # Список логов этого типа
    logs: Mapped[List["Log"]] = relationship(
        back_populates="log_type",
        cascade="all, delete-orphan",
        init=False
    )

    def __repr__(self) -> str:
        return f"LogType({self.name})"


class Log(Base):
    __tablename__ = "log"

    id: Mapped[str] = mapped_column(
        sa.Uuid(as_uuid=False),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
        init=False
    )

    # Время
    date_time: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=False,
        server_default=sa.text("NOW()"),
        init=False
    )

    # Тип лога
    log_type_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.log_type.id"),
        nullable=False
    )

    # Тип лога
    log_type: Mapped["LogType"] = relationship(
        back_populates="logs",
        lazy="noload",
        init=False
    )

    # Сообщение
    message: Mapped[str] = mapped_column(
        sa.String(),
        nullable=False
    )

    # Подробности
    details: Mapped[str] = mapped_column(
        sa.String(),
        nullable=False,
        server_default='',
        init=False
    )

    # Имя пользователя
    username: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        server_default='',
        init=False
    )

    # Предыдущее состояние
    previous_state: Mapped[str] = mapped_column(
        sa.String(),
        nullable=False,
        server_default='',
        init=False
    )

    # Новое состояние
    new_state: Mapped[str] = mapped_column(
        sa.String(),
        nullable=False,
        server_default='',
        init=False
    )

    def __repr__(self) -> str:
        return f"Log({self.message})"
