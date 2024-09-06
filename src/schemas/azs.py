from typing import Annotated

from pydantic import Field

from src.database.models.azs import AzsOwnType
from src.schemas.base import BaseSchema


# code_ = Annotated[str, Field(description="Код АЗС")]
# is_active_ = Annotated[bool | None, Field(description="АЗС осуществляет деятельность", examples=[True])]
# country_code_ = Annotated[str | None, Field(description="Код страны")]
# region_code_ = Annotated[str | None, Field(description="Код региона")]
# is_franchisee_ = Annotated[bool | None, Field(description="Франчайзи")]
# latitude_ = Annotated[float | None, Field(description="Координаты – широта")]
# longitude_ = Annotated[float | None, Field(description="Координаты – долгота")]


class AzsReadMinSchema(BaseSchema):
    id: Annotated[str, Field(description="UUID АЗС")]
    external_id: Annotated[str, Field(description="Идентификатор АЗС в системе поставщика")]
    name: Annotated[str, Field(description="Наименование")]
    own_type: Annotated[AzsOwnType | None, Field(description="Тип АЗС")]
    pretty_address: Annotated[str | None, Field(description="Адрес")]
