from typing import Annotated, List

from pydantic import Field, ConfigDict, Extra, BaseModel

from src.database.models.card_limit import Unit, LimitPeriod
from src.database.models.goods_category import GoodsCategory
from src.schemas.base import BaseSchema
from src.schemas.goods import InnerGoodsGroupReadSchema
from src.schemas.validators import UnitByName, LimitPeriodByName, GoodsCategoryByName, EmptyStrToNone


class GoodsGroupSchema(BaseSchema):
    id: Annotated[str, Field(description="UUID группы продуктов в нашей системе",
                             examples=["68425199-ac93-4733-becb-de2e89e85303"])]
    name: Annotated[str, Field(description="Наименование группы продуктов в нашей системе", examples=["Бензины"])]
    base_unit: Annotated[UnitByName | None, Field(description="Базовая единица измерения", examples=["LITERS"])]


class AzsOwnTypesSchema(BaseSchema):
    id: Annotated[str, Field(description="ID типа АЗС")]
    name: Annotated[str, Field(description="Наименование типа АЗС")]


class GoodsCategorySchema(BaseSchema):
    id: Annotated[str, Field(description="Код категории продуктов в нашей системе", examples=["FUEL"])]
    name: Annotated[str, Field(description="Наименование категория продуктов в нашей системе", examples=["Топливо"])]
    groups: Annotated[List[GoodsGroupSchema], Field(description="Группа продуктов в нашей системе")]


class UnitSchema(BaseSchema):
    id: Annotated[str, Field(description="Код единицы измерения", examples=["ITEMS"])]
    name: Annotated[str, Field(description="Наименование единицы измерения", examples=["шт"])]
    type: Annotated[str, Field(description="Тип единицы измерения (базовый или добавляемый)", examples=["base"])]


class PeriodSchema(BaseSchema):
    id: Annotated[str, Field(description="Код периода", examples=["MONTH"])]
    name: Annotated[str, Field(description="Наименование периода", examples=["месяц"])]


class CardLimitParamsSchema(BaseSchema):
    categories: Annotated[List[GoodsCategorySchema], Field(description="Категория продуктов в нашей системе")]
    units: Annotated[List[UnitSchema], Field(description="Единицы измерения")]
    periods: Annotated[List[PeriodSchema], Field(description="Единицы измерения")]


class CardLimitCreateSchema(BaseSchema):
    value: Annotated[int, Field(description="Значение лимита", examples=["57000"])]
    unit: Annotated[UnitByName, Field(description="Единицы измерения")]
    period: Annotated[LimitPeriodByName, Field(description="Период")]
    inner_goods_group_id: Annotated[EmptyStrToNone | None, Field(description="UUID лимита")] = None
    inner_goods_category: Annotated[GoodsCategoryByName | None, Field(description="UUID лимита")] = None


class CardLimitReadSchema(BaseModel):
    id: Annotated[str | None, Field(description="UUID лимита")]
    card_id: Annotated[str, Field(description="UUID топливной карты")]
    value: Annotated[int, Field(description="Значение лимита", examples=["57000"])]
    unit: Annotated[Unit, Field(description="Единицы измерения")]
    period: Annotated[LimitPeriod, Field(description="Период")]
    inner_goods_group: Annotated[InnerGoodsGroupReadSchema | None, Field(
        description="UUID группы продуктов в нашей системе")]
    inner_goods_category: Annotated[GoodsCategory | None, Field(description="Категория продуктов в нашей системе")]

    model_config = ConfigDict(
        from_attributes=True,
        extra=Extra.ignore,
        json_encoders={
            GoodsCategory: lambda category: category.name,
            Unit: lambda unit: unit.name,
            LimitPeriod: lambda period: period.name,
        }
    )
