from datetime import date
from typing import List, Annotated

from pydantic import Field

from src.schemas.balance import BalanceReadSchema
from src.schemas.base import BaseSchema
from src.schemas.role import RoleReadMinimumSchema


class CompanyUserSchema(BaseSchema):
    id: Annotated[str, Field(description="UUID пользователя", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]
    username: Annotated[str, Field(description="Имя пользователя", examples=["user"])]
    first_name: Annotated[str, Field(description="Имя", examples=["Алексей"])]
    last_name: Annotated[str, Field(description="Фамилия", examples=["Гагарин"])]
    phone: Annotated[str, Field(description="Телефон", examples=["+79332194370"])]
    role: Annotated[RoleReadMinimumSchema, Field(description="Роль")]


class CompanyCarSchema(BaseSchema):
    id: Annotated[str, Field(description="UUID автомобиля", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]
    model: Annotated[str, Field(description="Марка/модель", examples=["Камаз"])]
    reg_number: Annotated[str, Field(description="Государственный регистрационный номер", examples=["Н314УР77"])]


id_ = Annotated[str, Field(description="UUID организации", examples=["20f06bf0-ae28-4f32-b2ca-f57796103a71"])]

name_ = Annotated[str | None, Field(description="Наименование", examples=['ООО "Современные технологии"'])]

inn_ = Annotated[str | None, Field(description="ИНН", examples=["77896534678800"])]

contacts_ = Annotated[str | None, Field(description="Контактные данные", examples=[""])]

personal_account_ = Annotated[str | None, Field(description="Лицевой счет", examples=["6590100"])]

date_add_ = Annotated[date | None, Field(description="Дата добавления в систему", examples=["2023-05-17"])]

cards_amount_ = Annotated[
    int | None,
    Field(description="Количество карт, принадлежащих этой организации", examples=[60])
]

users_ = Annotated[List[CompanyUserSchema], Field(description="Список пользователей этой организации")]

balances_ = Annotated[List[BalanceReadSchema], Field(description="Список балансов этой организации")]

cars_ = Annotated[List[CompanyCarSchema], Field(description="Список пользователей этой организации")]


class CompanyEditSchema(BaseSchema):
    contacts: contacts_ = None
    name: name_ = None
    inn: inn_ = None


class CompanyReadMinimumSchema(BaseSchema):
    id: id_
    name: name_
    inn: inn_


class CompanyReadSchema(BaseSchema):
    id: id_
    name: name_
    inn: inn_
    personal_account: personal_account_
    date_add: date_add_
    cards_amount: cards_amount_ = None
    users: users_ = []
    balances: balances_ = []
    cars: cars_ = []


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
