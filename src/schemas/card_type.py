from typing import Annotated

from pydantic import Field

from src.schemas.base import BaseSchema

id_ = Annotated[str, Field(description="UUID типа карт", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]
name_ = Annotated[str, Field(description="Наименование типа карт", examples=["Пластиковая карта"])]


class CardTypeReadSchema(BaseSchema):
    id: id_
    name: name_


class CardTypeCreateSchema(BaseSchema):
    name: name_


class CardTypeEditSchema(BaseSchema):
    name: name_
