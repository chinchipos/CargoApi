from datetime import datetime
from typing import Annotated, List

from pydantic import Field

from src.database.models.goods_category import GoodsCategory
from src.schemas.azs import AzsReadMinSchema
from src.schemas.base import BaseSchema
from src.schemas.goods import InnerGoodsGroupReadSchema
from src.schemas.system import SystemReadMinimumSchema

id_ = Annotated[str, Field(description="UUID тарифа", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]

name_ = Annotated[str, Field(description="Наименование", examples=["ННК 0,5%"])]

fee_percent_ = Annotated[float, Field(description="Комиссия, %", examples=[0.5])]

policy_id_ = Annotated[str, Field(description="UUID тарифной политики",
                                  examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]

policy_name_ = Annotated[str, Field(description="Наименование тарифной политики", examples=["ННК 0,5%"])]

policy_is_active_ = Annotated[bool, Field(description="Тарифная политика активна", examples=[True])]

tariff_id_ = Annotated[str, Field(description="UUID тарифа",  examples=["e455c5c-b980-45eb-a192-585e6823c7aa"])]

inner_category_ = Annotated[GoodsCategory | None, Field(
    description="Категория товаров в нашей системе", examples=["Топливо"])]

discount_fee_ = Annotated[float, Field(description="Скидка/наценка",  examples=[-1.5])]

discount_fee_franchisee_ = Annotated[float, Field(description="Скидка/наценка для фрашчайзи",  examples=[5.0])]

begin_time_ = Annotated[datetime, Field(description="Дата создания (начала действия)", examples=["2023-05-17"])]

end_time_ = Annotated[datetime | None, Field(description="Дата архивации (прекращения действия)",
                                             examples=["2024-05-17"])]


class TariffCreateSchema(BaseSchema):
    name: name_
    fee_percent: fee_percent_


class TariffEditSchema(BaseSchema):
    name: name_


class TariffMinimumReadSchema(BaseSchema):
    id: id_
    name: name_


class TariffReadSchema(BaseSchema):
    id: id_
    name: name_
    fee_percent: fee_percent_


class TariffNewReadSchema(BaseSchema):
    id: tariff_id_
    system: Annotated[SystemReadMinimumSchema , Field(description="Система")]
    inner_goods_group: Annotated[InnerGoodsGroupReadSchema | None, Field(description="Категория продуктов в нашей системе")]
    inner_goods_category: inner_category_
    azs: Annotated[AzsReadMinSchema | None, Field(description="АЗС")]
    discount_fee: discount_fee_
    discount_fee_franchisee: discount_fee_franchisee_
    begin_time: begin_time_
    end_time: end_time_


class TariffPolicyReadSchema(BaseSchema):
    id: policy_id_
    name: policy_name_
    is_active: policy_is_active_
    tariffs: Annotated[List[TariffNewReadSchema], Field(description="Тариф")]
