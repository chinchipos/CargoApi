from pydantic import BaseModel, ConfigDict


class CardReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    fee_percent: float
    companies_amount: int


class CardCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    fee_percent: float


class CardEditSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
