from typing import List

import sqlalchemy as sa
from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models import Base


class UserOrm(SQLAlchemyBaseUserTableUUID, Base):
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
    role: Mapped["RoleOrm"] = relationship(
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
    company: Mapped["CompanyOrm"] = relationship(
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
    admin_company: Mapped[List["AdminCompanyOrm"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список автомобилей привязанных к этому пользователю
    # в случае, если он обладает ролью Водитель
    car_driver: Mapped[List["CarDriverOrm"]] = relationship(
        back_populates="driver",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список карт, привязанных к этому пользователю
    cards: Mapped[List["CardOrm"]] = relationship(
        back_populates="belongs_to_driver",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список отчетов, сгенерированных этим пользователем
    reports: Mapped[List["CheckReportOrm"]] = relationship(
        back_populates="user",
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
            sa.select(AdminCompanyOrm.id)
            .where(AdminCompanyOrm.user_id == self.id)
            .subquery()
        )
        return stmt


class AdminCompanyOrm(Base):
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
    user: Mapped["UserOrm"] = relationship(
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
    company: Mapped["CompanyOrm"] = relationship(
        back_populates="admin_company",
        lazy="noload",
        init = False
    )
