from typing import Optional

from pydantic import BaseModel, ConfigDict


class CardTypeReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


class CardTypeCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str


class CardTypeEditSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: Optional[str] = None