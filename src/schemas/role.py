from typing import Annotated

from pydantic import Field

from src.schemas.base import BaseSchema
from src.utils.enums import Role

id_ = Annotated[str, Field(description="UUID роли", examples=["cf939780-75b2-4762-ab4d-df71289f5e8a"])]

name_ = Annotated[str, Field(description="Условное обозначение роли", examples=[Role.COMPANY_LOGIST.name])]

title_ = Annotated[
    str,
    Field(description="Отображаемое наименование роли", examples=[Role.COMPANY_LOGIST.value['title']])
]

description_ = Annotated[
    str,
    Field(description="Описание роли",
          examples=[(
              "Сотрудник организации. Имеет право просматривать определенный список карт этой организации, "
              "менять лимиты, создавать водителей."
          )])
]


class RoleReadSchema(BaseSchema):
    id: id_
    name: name_
    title: title_
    description: description_
