from typing import Annotated

from pydantic import Field

from src.schemas.base import BaseSchema


class RegionReadSchema(BaseSchema):
    id: Annotated[str, Field(description="UUID АЗС")]
    name: Annotated[str, Field(description="Регион")]
    country: Annotated[str, Field(description="Страна")]
