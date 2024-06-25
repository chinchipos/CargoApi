from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class TariffReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Annotated[str, Field(description="UUID тарифа", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]
    name: Annotated[str, Field(description="Наименование", examples=["ННК 0,5%"])]
    fee_percent: Annotated[float, Field(description="Комиссия, %", examples=[0.5])]
    companies_amount: Annotated[int, Field(description="Количество организаций с этим тарифом", examples=[27])]


class TariffMinimumReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Annotated[str, Field(description="UUID тарифа", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]
    name: Annotated[str, Field(description="Наименование", examples=["ННК 0,5%"])]


class TariffCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: Annotated[str, Field(description="Наименование", examples=["ННК 0,5%"])]
    fee_percent: Annotated[float, Field(description="Комиссия, %", examples=[0.5])]


class TariffEditSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: Annotated[str, Field(description="Наименование", examples=["ННК 0,5%"])]
