from typing import Optional

from pydantic import BaseModel, ConfigDict

from src.schemas.system import SystemReadMinimumSchema


class InnerGoodsReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


class OuterGoodsReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    inner_goods: Optional[InnerGoodsReadSchema] = None
    system: Optional[SystemReadMinimumSchema] = None
