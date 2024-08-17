from typing import List

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base


class PermitionOrm(Base):
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
    role_permition: Mapped[List["RolePermitionOrm"]] = relationship(
        back_populates="permition",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    repr_cols = ("name",)


class RoleOrm(Base):
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
    users: Mapped[List["UserOrm"]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список прав для этой роли
    role_permition: Mapped[List["RolePermitionOrm"]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    repr_cols = ("title",)

    def has_permition(self, permition: PermitionOrm) -> bool:
        if not self.role_permition:
            return False

        if permition in [rp.permition.name.upper() for rp in self.role_permition]:
            return True
        else:
            return False


class RolePermitionOrm(Base):
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
    role: Mapped["RoleOrm"] = relationship(
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
    permition: Mapped["PermitionOrm"] = relationship(
        back_populates="role_permition",
        lazy="noload",
        init=False
    )

    repr_cols = ("role_id", "permition_id")
