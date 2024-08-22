from datetime import datetime
from typing import Annotated

from pydantic import BeforeValidator, Field

from src.database.models.balance import BalanceOrm
from src.database.models.card_limit import Unit, LimitPeriod
from src.schemas.base import BaseSchema


def empty_str_to_none(value: str):
    return None if value == '' else value


EmptyStrToNone = Annotated[str | None, BeforeValidator(empty_str_to_none)]


def normalize_date_time(value: datetime):
    return value.isoformat(sep=' ', timespec='seconds') if value else None


DateTimeNormalized = Annotated[str | None, BeforeValidator(normalize_date_time)]


def company_from_balance(balance: BalanceOrm):
    return balance.company


class CompanyMinimumSchema(BaseSchema):
    id: Annotated[str, Field(description="UUID организации", examples=["20f06bf0-ae28-4f32-b2ca-f57796103a71"])]
    name: Annotated[str | None, Field(description="Наименование", examples=['ООО "Современные технологии"'])]
    inn: Annotated[str | None, Field(description="ИНН", examples=["77896534678800"])]
    personal_account: Annotated[str | None, Field(description="Лицевой счет", examples=["6590100"])]


CompanyFromBalance = Annotated[CompanyMinimumSchema | None, BeforeValidator(company_from_balance)]


def negative_to_positive(value: float | int | str | None) -> float | int | str | None:
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            return None

    if isinstance(value, float) or isinstance(value, int):
        return value * -1 if value and value < 0 else value


NegativeToPositive = Annotated[float | int | None, BeforeValidator(negative_to_positive)]


def positive_to_negative(value: float | int | str | None) -> float | int | str | None:
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            return None

    if isinstance(value, float) or isinstance(value, int):
        return value * -1 if value and value > 0 else value


PositiveToNegative = Annotated[float | int | None, BeforeValidator(positive_to_negative)]


def unit_name_by_value(unit: str | None) -> str | None:
    if unit == Unit.ITEMS.value:
        return Unit.ITEMS.name

    elif unit == Unit.LITERS.value:
        return Unit.LITERS.name

    elif unit == Unit.RUB.value:
        return Unit.RUB.name


UnitNameByValue = Annotated[str | None, BeforeValidator(unit_name_by_value)]


def limit_period_name_by_value(period: str | None) -> str | None:
    if period == LimitPeriod.DAY.value:
        return LimitPeriod.DAY.name

    elif period == LimitPeriod.MONTH.value:
        return LimitPeriod.MONTH.name


LimitPeriodNameByValue = Annotated[str | None, BeforeValidator(limit_period_name_by_value)]
