from datetime import datetime
from typing import Annotated, List, Dict, Any

from pydantic import Field

from src.schemas.base import BaseSchema


class CheckReportSchema(BaseSchema):
    id: Annotated[str, Field(description="UUID")]
    report_type: Annotated[str, Field(description="Тип отчета")]
    description: Annotated[str, Field(description="Описание")]
    creation_time: Annotated[datetime, Field(description="Время формирования")]
    data: Annotated[List[Dict[str, Any]], Field(description="Данные")]


class CheckReportMinSchema(BaseSchema):
    id: Annotated[str, Field(description="UUID")]
    creation_time: Annotated[datetime, Field(description="Время формирования")]


class CheckReportTypeSchema(BaseSchema):
    name: Annotated[str, Field(description="Тип отчета")]
    description: Annotated[str, Field(description="Описание")]
    versions: Annotated[List[CheckReportMinSchema], Field(description="Варианты отчета")] = None
