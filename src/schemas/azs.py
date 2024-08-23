from typing import Annotated

from pydantic import Field

from src.schemas.base import BaseSchema

azs_id_ = Annotated[str, Field(description="UUID АЗС",  examples=["e455c5c-b980-45eb-a192-585e6823c7aa"])]
name_ = Annotated[str, Field(description="Название АЗС")]
code_ = Annotated[str, Field(description="Код АЗС")]
is_active_ = Annotated[bool | None, Field(description="АЗС осуществляет деятельность", examples=[True])]
country_code_ = Annotated[str | None, Field(description="Код страны")]
region_code_ = Annotated[str | None, Field(description="Код региона")]
address_ = Annotated[str, Field(description="Адрес")]
is_franchisee_ = Annotated[bool | None, Field(description="Франчайзи")]
latitude_ = Annotated[float | None, Field(description="Координаты – широта")]
longitude_ = Annotated[float | None, Field(description="Координаты – долгота")]


class AzsReadMinSchema(BaseSchema):
    id: azs_id_
    name: name_
    code: code_
    is_active: is_active_
    country_code: country_code_
    region_code: region_code_
    address: address_
    is_franchisee: is_franchisee_
    latitude: latitude_
    longitude: longitude_
