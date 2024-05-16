from pydantic import BaseModel, ConfigDict


class TariffReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    fee_percent: float
    companies_amount: int


class TariffMinimumReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


class TariffCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    fee_percent: float


class TariffEditSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
