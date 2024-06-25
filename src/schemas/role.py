from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.utils.enums import Role


class RoleReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Annotated[str, Field(description="UUID роли", examples=["cf939780-75b2-4762-ab4d-df71289f5e8a"])]
    name: Annotated[str, Field(description="Условное обозначение роли", examples=[Role.COMPANY_LOGIST.name])]
    title: Annotated[str, Field(
        description="Отображаемое наименование роли",
        examples=[Role.COMPANY_LOGIST.value['title']]
    )]
    description: Annotated[str, Field(
        description="Описание роли",
        examples=[(
            "Сотрудник организации. Имеет право просматривать определенный список карт этой организации, "
            "менять лимиты, создавать водителей."
        )]
    )]
