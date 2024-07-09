from datetime import date
from typing import List, Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.balance import BalanceReadSchema
from src.schemas.base import BaseSchema
from src.schemas.role import RoleReadSchema


class CompanyBaseSchema(BaseSchema):

    name: Annotated[
        str | None,
        Field(
            description="Наименование",
            examples=['ООО "Современные технологии"'])
    ] = None

    inn: Annotated[
        str | None,
        Field(
            description="ИНН",
            examples=["77896534678800"])
    ] = None


class CompanyEditSchema(CompanyBaseSchema):

    contacts: Annotated[
        str | None,
        Field(
            description="Контактные данные",
            examples=[""])
    ] = None


class CompanyReadMinimumSchema(CompanyBaseSchema):

    id: Annotated[
        str,
        Field(
            description="UUID организации",
            examples=["20f06bf0-ae28-4f32-b2ca-f57796103a71"])
    ]


class CompanyUserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Annotated[str, Field(description="UUID пользователя", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]
    username: Annotated[str, Field(description="Имя пользователя", examples=["user"])]
    first_name: Annotated[str, Field(description="Имя", examples=["Алексей"])]
    last_name: Annotated[str, Field(description="Фамилия", examples=["Гагарин"])]
    phone: Annotated[str, Field(description="Телефон", examples=["+79332194370"])]
    role: Annotated[RoleReadSchema, Field(description="Роль")]


class CompanyReadSchema(CompanyReadMinimumSchema):

    personal_account: Annotated[
        str | None,
        Field(
            description="Лицевой счет",
            examples=["6590100"])
    ] = None

    date_add: Annotated[
        date | None,
        Field(
            description="Дата добавления в систему",
            examples=["2023-05-17"])
    ] = None

    cards_amount: Annotated[
        int | None,
        Field(
            description="Количество карт, принадлежащих этой организации",
            examples=[271886.33])
    ] = None

    users: Annotated[
        List[CompanyUserSchema] | None,
        Field(description="Список пользователей этой организации")
    ] = None

    balances: Annotated[
        List[BalanceReadSchema] | None,
        Field(description="Список балансов этой организации")
    ] = None


"""
class CompanyBalanceEditSchema(BaseSchema):

    direction: Annotated[
        enums.Finance,
        Field(
            description="Операция дебетования/кредитования",
            examples=[enums.Finance.DEBIT.value])
    ]

    delta_sum:  Annotated[
        float,
        Field(
            description="Сумма корректировки, руб",
            examples=[5000.0], gt=0)
    ]
"""
