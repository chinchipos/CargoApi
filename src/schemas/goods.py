from typing import Optional, Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.system import SystemReadMinimumSchema
from src.schemas.validators import EmptyStrToNone


class InnerGoodsReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Annotated[str, Field(
        description="UUID товара/услуги в локальной системе",
        examples=["68425199-ac93-4733-becb-de2e89e85303"])
    ]
    name: Annotated[str, Field(description="Локальное наименование", examples=["ДТ-З-К5"])]


class InnerGoodsEditSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    inner_name: Annotated[
        Optional[EmptyStrToNone], Field(description="Локальное наименование", examples=["ДТ-З-К5"])
    ] = ''


class OuterGoodsReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Annotated[str, Field(
        description="UUID товара/услуги в системе поставщика услуг",
        examples=["03aa8565-e701-4501-86a9-cc8c9c99ecb7"])
    ]
    name: Annotated[str, Field(description="Наименование в системе поставщика услуг", examples=["ДТЗК5"])]
    inner_goods: Annotated[Optional[InnerGoodsReadSchema], Field(description="Товара/услуга локальной системы")] = []
    system: Annotated[Optional[SystemReadMinimumSchema], Field(description="Поставщик услуг")] = None
