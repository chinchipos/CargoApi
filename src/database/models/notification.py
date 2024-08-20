from typing import List

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base
from datetime import date, datetime


class NotificationOrm(Base):
    __tablename__ = "notification"
    __table_args__ = {
        'comment': "Уведомления"
    }

    date_create: Mapped[date] = mapped_column(
        sa.Date,
        nullable=False,
        init=False,
        server_default=sa.text("NOW()"),
        comment="Дата создания"
    )

    caption: Mapped[str] = mapped_column(
        sa.String(),
        nullable=False,
        init=True,
        comment="Заголовок"
    )

    text: Mapped[str] = mapped_column(
        sa.String(),
        nullable=False,
        init=True,
        comment="Текст"
    )

    # Список уведомлений этой организации
    notification_mailings: Mapped[List["NotificationMailingOrm"]] = relationship(
        back_populates="notification",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False
    )


class NotificationMailingOrm(Base):
    __tablename__ = "notifcation_mailing"
    __table_args__ = {
        'comment': "Рассылка уведомлений"
    }

    date_time_read: Mapped[datetime] = mapped_column(
        sa.Date,
        nullable=True,
        comment="Время прочтения"
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
        back_populates="notification_mailings",
        lazy="noload",
        init=False
    )

    # Уведомление
    notification_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.notification.id"),
        nullable=False,
        init=True,
        comment="Уведомление"
    )

    # Уведомление
    notification: Mapped["NotificationOrm"] = relationship(
        back_populates="notification_mailings",
        lazy="noload",
        init=False
    )
