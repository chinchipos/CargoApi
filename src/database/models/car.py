from typing import List

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base


class CarOrm(Base):
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
    company: Mapped["CompanyOrm"] = relationship(
        back_populates="cars",
        lazy="noload",
        init=False
    )

    # Список карт привязанных к этому автомобилю
    cards: Mapped[List["CardOrm"]] = relationship(
        back_populates="belongs_to_car",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )

    # Список водителей привязанных к этому автомобилю
    car_driver: Mapped[List["CarDriverOrm"]] = relationship(
        back_populates="car",
        cascade="all, delete-orphan",
        init=False
    )


class CarDriverOrm(Base):
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
    car: Mapped["CarOrm"] = relationship(
        back_populates="car_driver",
        lazy="noload"
    )

    driver_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.user.id"),
        nullable=False,
        comment="Водитель"
    )

    # Водитель
    driver: Mapped["UserOrm"] = relationship(
        back_populates="car_driver",
        lazy="noload"
    )
