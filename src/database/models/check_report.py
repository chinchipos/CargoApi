from datetime import datetime
from enum import Enum
from typing import Any, Dict

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from src.database.models.base import Base


class CheckReport(Enum):
    GPN_GROUP_LIMITS = {"description": "Контроль правильности установки групповых лимитов ГПН"}


class CheckReportOrm(Base):
    __tablename__ = "check_report"
    __table_args__ = (
        {'comment': 'Отчеты для мониторинга правильности функционирования системы'}
    )

    report_type: Mapped[CheckReport] = mapped_column(
        ENUM(CheckReport, name="checkreport"),
        nullable=False,
        init=True,
        comment="Тип отчета"
    )

    data: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        init=True,
        comment="Данные"
    )

    user_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.user.id"),
        nullable=True,
        init=True,
        default=None,
        comment="Пользователь, которому доступен сформированный отчет"
    )

    role_id: Mapped[str] = mapped_column(
        sa.ForeignKey("cargonomica.role.id"),
        nullable=True,
        init=True,
        default=None,
        comment="Роль, которой доступен сформированный отчет"
    )

    creation_time: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=False,
        server_default=sa.text("NOW()"),
        init=False,
        comment="Время формирования"
    )

    user: Mapped["UserOrm"] = relationship(
        back_populates="reports",
        lazy="noload",
        init=False
    )

    role: Mapped["RoleOrm"] = relationship(
        back_populates="reports",
        lazy="noload",
        init=False
    )
