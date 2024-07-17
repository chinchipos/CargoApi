from datetime import datetime
from typing import Annotated

from pydantic import BeforeValidator, AfterValidator, Field

from src.database.models import Balance as BalanceModel
from src.schemas.base import BaseSchema


def empty_str_to_none(value: str):
    return None if value == '' else value


EmptyStrToNone = Annotated[str | None, BeforeValidator(empty_str_to_none)]


def normalize_date_time(value: datetime):
    return value.isoformat(sep=' ', timespec='seconds') if value else None


DateTimeNormalized = Annotated[str | None, BeforeValidator(normalize_date_time)]


def company_from_balance(balance: BalanceModel):
    return balance.company


class CompanyMinimumSchema(BaseSchema):
    id: Annotated[str, Field(description="UUID организации", examples=["20f06bf0-ae28-4f32-b2ca-f57796103a71"])]
    name: Annotated[str | None, Field(description="Наименование", examples=['ООО "Современные технологии"'])]
    inn: Annotated[str | None, Field(description="ИНН", examples=["77896534678800"])]


CompanyFromBalance = Annotated[CompanyMinimumSchema | None, BeforeValidator(company_from_balance)]
