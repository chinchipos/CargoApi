from typing import Optional

from pydantic import BaseModel, ConfigDict

from src.schemas.system import SystemReadMinimumSchema


class InnerGoodsReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


class InnerGoodsEditSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    inner_name: Optional[str] = ''


class OuterGoodsReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    inner_goods: Optional[InnerGoodsReadSchema] = []
    system: Optional[SystemReadMinimumSchema] = None
