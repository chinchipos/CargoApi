from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.base import BaseSchema


class TariffBaseSchema(BaseSchema):

    name: Annotated[
        str,
        Field(
            description="Наименование",
            examples=["ННК 0,5%"])
    ]


class TariffCreateSchema(TariffBaseSchema):

    fee_percent: Annotated[
        float,
        Field(
            description="Комиссия, %",
            examples=[0.5])
    ]


class TariffMinimumReadSchema(TariffBaseSchema):

    id: Annotated[
        str, Field(
            description="UUID тарифа",
            examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])
    ]


class TariffReadSchema(TariffMinimumReadSchema, TariffCreateSchema):
    ...
