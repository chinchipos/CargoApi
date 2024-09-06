from datetime import datetime
from typing import Annotated, List

from pydantic import Field

from src.database.models.goods_category import GoodsCategory
from src.schemas.azs import AzsReadMinSchema
from src.schemas.base import BaseSchema
from src.schemas.card_limit import GoodsCategorySchema, AzsOwnTypesSchema
from src.schemas.goods import InnerGoodsGroupReadSchema
from src.schemas.region import RegionReadSchema
from src.schemas.system import SystemReadMinimumSchema
from src.schemas.validators import GoodsCategoryByName, EmptyStrToNone, GoodsCategoryToDict, AzsOwnTypeToDict, \
    AzsOwnTypeByName

id_ = Annotated[str, Field(description="UUID тарифа", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]

name_ = Annotated[str, Field(description="Наименование", examples=["ННК 0,5%"])]

fee_percent_ = Annotated[float, Field(description="Комиссия, %", examples=[0.5])]

policy_id_ = Annotated[str, Field(description="UUID тарифной политики",
                                  examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]

policy_name_ = Annotated[str, Field(description="Наименование тарифной политики", examples=["ННК 0,5%"])]

policy_is_active_ = Annotated[bool, Field(description="Тарифная политика активна", examples=[True])]

tariff_id_ = Annotated[str | None, Field(description="UUID тарифа",  examples=["e455c5c-b980-45eb-a192-585e6823c7aa"])]

inner_category_ = Annotated[GoodsCategory | None, Field(
    description="Категория товаров в нашей системе", examples=["Топливо"])]

discount_fee_ = Annotated[float, Field(description="Скидка/наценка",  examples=[-1.5])]

begin_time_ = Annotated[datetime, Field(description="Дата создания (начала действия)", examples=["2023-05-17"])]

end_time_ = Annotated[datetime | None, Field(description="Дата архивации (прекращения действия)",
                                             examples=["2024-05-17"])]

system_id_ = Annotated[str, Field(description="UUID истемы")]
system_ = Annotated[SystemReadMinimumSchema, Field(description="Система")]

inner_goods_group_id_ = Annotated[EmptyStrToNone, Field(description="UUID группы продуктов в нашей системе")]
inner_goods_group_ = Annotated[
    InnerGoodsGroupReadSchema | None, Field(description="Группа продуктов в нашей системе")]

azs_ids_ = Annotated[List[str] | None, Field(description="UUID АЗС")]
azs_ = Annotated[AzsReadMinSchema | None, Field(description="АЗС")]

region_id_ = Annotated[EmptyStrToNone, Field(description="UUID Региона")]
region_ = Annotated[RegionReadSchema | None, Field(description="Регион")]

azs_own_type_ = Annotated[AzsOwnTypeByName | None, Field(description="Тип АЗС")]

goods_category_ = Annotated[GoodsCategoryByName | None, Field(description="Категория продуктов")]


class TariffCreateSchema(BaseSchema):
    name: name_
    fee_percent: fee_percent_


class TariffEditSchema(BaseSchema):
    name: name_


class TariffPolicyReadMinSchema(BaseSchema):
    id: policy_id_
    name: policy_name_


class TariffNewReadMinSchema(BaseSchema):
    id: tariff_id_
    policy: Annotated[TariffPolicyReadMinSchema | None, Field(description="Тарифная политика")] = None


class TariffNewReadSchema(BaseSchema):
    id: tariff_id_
    system: system_
    inner_goods_group: inner_goods_group_
    inner_goods_category: Annotated[GoodsCategoryToDict | None, Field(description="Справочник категорий продуктов")]
    azs: azs_
    region: region_
    azs_own_type: Annotated[AzsOwnTypeToDict | None, Field(description="Справочник типов АЗС")]
    discount_fee: discount_fee_
    begin_time: begin_time_
    end_time: end_time_


class TariffPolicyReadSchema(BaseSchema):
    id: policy_id_
    name: policy_name_
    is_active: policy_is_active_
    tariffs: Annotated[List[TariffNewReadSchema] | None, Field(description="Тариф")] = None


class TariffDictionariesSchema(BaseSchema):
    polices: Annotated[List[TariffPolicyReadSchema] | None, Field(description="Тарифные политики")] = None
    systems: Annotated[List[SystemReadMinimumSchema] | None, Field(description="Справочник систем")] = None
    # azs_stations: Annotated[List[AzsReadMinSchema] | None, Field(description="Справочник АЗС")] = None
    azs_own_types: Annotated[List[AzsOwnTypesSchema] | None, Field(description="Справочник типов АЗС")] = None
    regions: Annotated[List[RegionReadSchema] | None, Field(description="Справочник Регионов")] = None
    goods_categories: Annotated[List[GoodsCategorySchema] | None, Field(
        description="Справочник категорий продуктов")] = None


class TariffPoliciesReadSchema(BaseSchema):
    polices: Annotated[List[TariffPolicyReadSchema], Field(description="Тарифные политики")]
    dictionaries: Annotated[TariffDictionariesSchema | None, Field(description="Справочники")] = None


class TariffParamsSchema(BaseSchema):
    tariff_id: tariff_id_ = None
    system_id: system_id_
    azs_ids: azs_ids_ = None
    region_id: region_id_ = None
    azs_own_type: azs_own_type_ = None
    goods_group_id: inner_goods_group_id_ = None
    goods_category: goods_category_ = None
    discount_fee: discount_fee_


class TariffNewCreateSchema(BaseSchema):
    policy_id: policy_id_ = None
    policy_name: policy_name_ = None
    tariffs: List[TariffParamsSchema]
