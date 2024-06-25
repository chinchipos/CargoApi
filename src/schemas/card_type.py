from typing import Optional, Annotated

from pydantic import BaseModel, ConfigDict, Field


class CardTypeReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Annotated[str, Field(description="UUID типа карт", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]
    name: Annotated[str, Field(description="Наименование типа карт", examples=["Пластиковая карта"])]


class CardTypeCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: Annotated[str, Field(description="Наименование типа карт", examples=["Пластиковая карта"])]


class CardTypeEditSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: Annotated[Optional[str], Field(description="Наименование типа карт", examples=["Пластиковая карта"])] = None
