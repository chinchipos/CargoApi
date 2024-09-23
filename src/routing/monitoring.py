import uuid
from typing import List

from fastapi import APIRouter, Depends

from src.depends import get_service_monitoring
from src.schemas.monitoring import CheckReportSchema, CheckReportTypeSchema
from src.services.monitoring import MonitoringService
from src.utils.enums import Role
from src.utils.exceptions import ForbiddenException
from src.utils.schemas import MessageSchema

router = APIRouter()
monitoring_tag_metadata = {
    "name": "monitoring",
    "description": "Мониторинг",
}


@router.get(
    path="/monitoring/get-reports",
    tags=["monitoring"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[CheckReportTypeSchema],
    summary = 'Получение списка отчетов для мониторинга',
    description = 'Получение списка отчетов для мониторинга'
)
async def get_reports(
    service: MonitoringService = Depends(get_service_monitoring)
):
    # Доступ имеют только суперадмины ПроАВТО
    if service.repository.user.role.name not in [Role.CARGO_SUPER_ADMIN.name]:
        raise ForbiddenException()

    reports = await service.get_reports()
    return reports


@router.get(
    path="/monitoring/get-report-types",
    tags=["monitoring"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[CheckReportTypeSchema],
    summary = 'Получение списка типов отчета для мониторинга',
    description = 'Получение списка типов отчета для мониторинга'
)
async def get_report_types(
    service: MonitoringService = Depends(get_service_monitoring)
):
    # Доступ имеют только суперадмины ПроАВТО
    if service.repository.user.role.name not in [Role.CARGO_SUPER_ADMIN.name]:
        raise ForbiddenException()

    report_types = await service.get_report_types()
    return report_types


@router.get(
    path="/monitoring/get-report/{id}",
    tags=["monitoring"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = CheckReportSchema,
    summary = 'Получение отчета',
    description = 'Получение отчета'
)
async def get_report(
    id: uuid.UUID,
    service: MonitoringService = Depends(get_service_monitoring)
):
    report_id = str(id)
    # Доступ имеют только суперадмины ПроАВТО
    if service.repository.user.role.name not in [Role.CARGO_SUPER_ADMIN.name]:
        raise ForbiddenException()

    report = await service.get_report(report_id=report_id)
    return report
