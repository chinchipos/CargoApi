from typing import Annotated

from pydantic import Field

from src.schemas.base import BaseSchema
from src.schemas.system import SystemReadMinimumSchema
from src.schemas.validators import EmptyStrToNone

inner_goods_id_ = Annotated[
    str,
    Field(description="UUID товара/услуги в локальной системе",
          examples=["68425199-ac93-4733-becb-de2e89e85303"])
]

inner_goods_name_ = Annotated[EmptyStrToNone, Field(description="Локальное наименование", examples=["ДТ-З-К5"])]

outer_goods_id_ = Annotated[
    str,
    Field(description="UUID товара/услуги в системе поставщика услуг",
          examples=["03aa8565-e701-4501-86a9-cc8c9c99ecb7"])
]

outer_goods_name_ = Annotated[str, Field(description="Наименование в системе поставщика услуг", examples=["ДТЗК5"])]

system_ = Annotated[SystemReadMinimumSchema | None, Field(description="Поставщик услуг")]


class InnerGoodsReadSchema(BaseSchema):
    id: inner_goods_id_
    name: inner_goods_name_


class InnerGoodsEditSchema(BaseSchema):
    inner_name: inner_goods_name_


class OuterGoodsReadSchema(BaseSchema):
    id: outer_goods_id_
    name: outer_goods_name_
    inner_goods: Annotated[InnerGoodsReadSchema | None, Field(description="Товара/услуга локальной системы")] = None
    system: system_ = None
