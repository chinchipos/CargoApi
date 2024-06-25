from datetime import datetime
from typing import Optional, Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.validators import DateTimeNormalized


class SystemReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Annotated[str, Field(description="UUID поставщика услуг", examples=["68425199-ac93-4733-becb-de2e89e85303"])]
    full_name: Annotated[str, Field(description="Полное наименование", examples=["Роснефть"])]
    short_name: Annotated[str, Field(description="Сокращенное наименование", examples=["РН"])]
    contract_num: Annotated[str, Field(description="Номер договора", examples=[""])]
    login: Annotated[str, Field(description="Логин для доступа", examples=["11111@rosneft.ru"])]
    transaction_days: Annotated[int, Field(description="Синхронизировать транзакции за период, дни", examples=[30])]
    balance: Annotated[float, Field(description="Баланс, руб", examples=[59327.98])]
    transactions_sync_dt: Annotated[
        Optional[DateTimeNormalized],
        Field(description="Время последней успешной синхронизации транзакции", examples=["2024-06-22 13:30:45"])
    ]
    cards_sync_dt: Annotated[
        Optional[DateTimeNormalized],
        Field(description="Время последней успешной синхронизации карт", examples=["2024-06-22 13:30:45"])
    ]
    balance_sync_dt: Annotated[
        Optional[DateTimeNormalized],
        Field(description="Время последней успешной синхронизации баланса", examples=["2024-06-22 13:30:45"])
    ]
    cards_amount: Annotated[int, Field(description="Кол-во карт этого поставщика услуг", examples=[750])]


class SystemReadMinimumSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Annotated[str, Field(description="UUID поставщика услуг", examples=["68425199-ac93-4733-becb-de2e89e85303"])]
    full_name: Annotated[str, Field(description="Полное наименование", examples=["Роснефть"])]
    short_name: Annotated[str, Field(description="Сокращенное наименование", examples=["РН"])]


class SystemCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    full_name: Annotated[str, Field(description="Полное наименование", examples=["Роснефть"])]
    short_name: Annotated[str, Field(description="Сокращенное наименование", examples=["РН"])]
    contract_num: Annotated[str, Field(description="Номер договора", examples=[""])]
    login: Annotated[str, Field(description="Логин для доступа", examples=["11111@rosneft.ru"])]
    password: Annotated[str, Field(description="Пароль", examples=["11111"])]
    transaction_days: Annotated[int, Field(
        description="Синхронизировать транзакции за период, дни",
        examples=[30])
    ] = 50


class SystemEditSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    full_name: Annotated[Optional[str], Field(description="Полное наименование", examples=["Роснефть"])] = None
    short_name: Annotated[Optional[str], Field(description="Сокращенное наименование", examples=["РН"])]
    contract_num: Annotated[Optional[str], Field(description="Номер договора", examples=[""])]
    login: Annotated[Optional[str], Field(description="Логин для доступа", examples=["11111@rosneft.ru"])]
    password: Annotated[Optional[str], Field(description="Пароль", examples=["11111"])]
    transaction_days: Annotated[Optional[int], Field(
        description="Синхронизировать транзакции за период, дни",
        examples=[30])
    ]

