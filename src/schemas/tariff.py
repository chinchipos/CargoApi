from typing import Annotated

from pydantic import Field

from src.schemas.base import BaseSchema

id_ = Annotated[str, Field(description="UUID тарифа", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]

name_ = Annotated[str, Field(description="Наименование", examples=["ННК 0,5%"])]

fee_percent_ = Annotated[float, Field(description="Комиссия, %", examples=[0.5])]


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
