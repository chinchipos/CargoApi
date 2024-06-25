from datetime import date
from typing import Optional, List, Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.role import RoleReadSchema
from src.utils import enums


class CompanyTariffSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Annotated[str, Field(description="UUID тарифа", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]
    name: Annotated[str, Field(description="Наименование", examples=["ННК 0,5%"])]
    fee_percent: Annotated[float, Field(description="Комиссия, %", examples=[0.5])]


class CompanyUserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Annotated[str, Field(description="UUID пользователя", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]
    username: Annotated[str, Field(description="Имя пользователя", examples=["user"])]
    first_name: Annotated[str, Field(description="Имя", examples=["Алексей"])]
    last_name: Annotated[str, Field(description="Фамилия", examples=["Гагарин"])]
    phone: Annotated[str, Field(description="Телефон", examples=["+79332194370"])]
    role: Annotated[RoleReadSchema, Field(description="Роль")]


class CompanyReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Annotated[str, Field(description="UUID организации", examples=["20f06bf0-ae28-4f32-b2ca-f57796103a71"])]
    name: Annotated[str, Field(description="Наименование", examples=['ООО "Современные технологии"'])]
    inn: Annotated[str, Field(description="ИНН", examples=["77896534678800"])]
    personal_account: Annotated[Optional[str], Field(description="Лицевой счет", examples=["6590100"])] = None
    contacts: Annotated[Optional[str], Field(description="Контактные данные", examples=[""])] = None
    date_add: Annotated[Optional[date], Field(description="Дата добавления в систему", examples=["2023-05-17"])] = None
    balance: Annotated[Optional[float], Field(description="Баланс", examples=[271886.33])] = None
    min_balance: Annotated[Optional[float], Field(
        description="Постоянный овердрафт (минимальный баланс), руб",
        examples=[10000.0])
    ] = None
    min_balance_on_period: Annotated[Optional[float], Field(
        description="Временный овердрафт (минимальный баланс), руб",
        examples=[30000.0])
    ] = None
    min_balance_period_end_date: Annotated[Optional[date], Field(
        description="Дата прекращения действия временного овердрафта",
        examples=["2023-05-17"])
    ] = None
    cards_amount: Annotated[Optional[int], Field(
        description="Количество карт, принадлежащих этой организации",
        examples=[271886.33])
    ] = None
    tariff: Annotated[Optional[CompanyTariffSchema], Field(description="Тариф")] = None
    users: Annotated[
        Optional[List[CompanyUserSchema]], Field(description="Список пользователей этой организации")
    ] = None


class CompanyReadMinimumSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Annotated[str, Field(description="UUID организации", examples=["20f06bf0-ae28-4f32-b2ca-f57796103a71"])]
    name: Annotated[str, Field(description="Наименование", examples=['ООО "Современные технологии"'])]
    inn: Annotated[str, Field(description="ИНН", examples=["77896534678800"])]


class CompanyEditSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: Annotated[Optional[str], Field(description="Наименование", examples=['ООО "Современные технологии"'])] = None
    inn: Annotated[Optional[str], Field(description="ИНН", examples=["77896534678800"])] = None
    tariff_id: Annotated[
        Optional[str], Field(description="UUID тарифа", examples=["287895d5-6aac-4493-9c28-99aec59bd804"])
    ] = None
    contacts: Annotated[
        Optional[str], Field(description="Контактные данные", examples=[""])
    ] = None
    min_balance: Annotated[Optional[float], Field(
        description="Постоянный овердрафт (минимальный баланс), руб",
        examples=[10000.0])
    ] = None
    min_balance_on_period: Annotated[Optional[float], Field(
        description="Временный овердрафт (минимальный баланс), руб",
        examples=[30000.0])
    ] = None
    min_balance_period_end_date: Annotated[Optional[date], Field(
        description="Дата прекращения действия временного овердрафта",
        examples=["2023-05-17"])
    ] = None


class CompanyBalanceEditSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    direction: Annotated[enums.Finance, Field(
        description="Операция дебетования/кредитования",
        examples=[enums.Finance.DEBIT.value])
    ]
    delta_sum:  Annotated[float, Field(description="Сумма корректировки, руб", examples=[5000.0], gt=0)]
