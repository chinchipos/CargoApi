from datetime import datetime
from typing import Annotated, Dict

from pydantic import BeforeValidator, Field, AfterValidator

from src.database.models.balance import BalanceOrm
from src.database.models.card_limit import Unit, LimitPeriod
from src.database.models.goods_category import GoodsCategory
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


def unit_by_name(unit: str | None) -> Unit | None:
    if unit == Unit.ITEMS.name:
        return Unit.ITEMS

    elif unit == Unit.LITERS.name:
        return Unit.LITERS

    elif unit == Unit.RUB.name:
        return Unit.RUB


UnitByName = Annotated[Unit | None, BeforeValidator(unit_by_name)]


def limit_period_by_name(period: str | None) -> LimitPeriod | None:
    if period == LimitPeriod.DAY.name:
        return LimitPeriod.DAY

    elif period == LimitPeriod.MONTH.name:
        return LimitPeriod.MONTH


LimitPeriodByName = Annotated[LimitPeriod | None, BeforeValidator(limit_period_by_name)]


def goods_category_by_name(category: str | None) -> GoodsCategory | None:
    if category == GoodsCategory.FUEL.name:
        return GoodsCategory.FUEL

    elif category == GoodsCategory.CAFE.name:
        return GoodsCategory.CAFE

    elif category == GoodsCategory.FOOD.name:
        return GoodsCategory.FOOD

    elif category == GoodsCategory.NON_FOOD.name:
        return GoodsCategory.NON_FOOD

    elif category == GoodsCategory.OTHER_SERVICES.name:
        return GoodsCategory.OTHER_SERVICES

    elif category == GoodsCategory.ROAD_PAYING.name:
        return GoodsCategory.ROAD_PAYING


GoodsCategoryByName = Annotated[GoodsCategory | None, BeforeValidator(goods_category_by_name)]


def goods_category_to_dict(category: GoodsCategory | None) -> Dict[str, str] | None:
    if category:
        return {"id": category.name, "name": category.value}


GoodsCategoryToDict = Annotated[GoodsCategory | Dict[str, str] | None, AfterValidator(goods_category_to_dict)]
