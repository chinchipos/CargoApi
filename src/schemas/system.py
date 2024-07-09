from typing import Annotated

from pydantic import Field

from src.schemas.base import BaseSchema
from src.schemas.validators import DateTimeNormalized


class SystemBaseSchema(BaseSchema):

    full_name: Annotated[
        str | None,
        Field(
            description="Полное наименование",
            examples=["Роснефть"])
    ] = None


class SystemEditSchema(SystemBaseSchema):

    transaction_days: Annotated[
        int | None,
        Field(
            description="Синхронизировать транзакции за период, дни (0 < x <= 50)",
            examples=[30],
            gt=0, le=50)
    ] = None


class SystemReadMinimumSchema(SystemBaseSchema):

    id: Annotated[
        str,
        Field(
            description="UUID поставщика услуг",
            examples=["68425199-ac93-4733-becb-de2e89e85303"])
    ]


class SystemReadSchema(SystemReadMinimumSchema, SystemEditSchema):

    balance: Annotated[
        float,
        Field(
            description="Баланс, руб",
            examples=[59327.98])
    ]

    transactions_sync_dt: Annotated[
        DateTimeNormalized | None,
        Field(
            description="Время последней успешной синхронизации транзакции",
            examples=["2024-06-22 13:30:45"])
    ] = None

    cards_sync_dt: Annotated[
        DateTimeNormalized | None,
        Field(
            description="Время последней успешной синхронизации карт",
            examples=["2024-06-22 13:30:45"])
    ] = None

    balance_sync_dt: Annotated[
        DateTimeNormalized | None,
        Field(
            description="Время последней успешной синхронизации баланса",
            examples=["2024-06-22 13:30:45"])
    ] = None

    cards_amount: Annotated[
        int,
        Field(
            description="Кол-во карт этого поставщика услуг",
            examples=[750])
    ]


"""
class SystemCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    full_name: Annotated[str, Field(description="Полное наименование", examples=["Роснефть"])]
    short_name: Annotated[str, Field(description="Сокращенное наименование", examples=["РН"])]
    transaction_days: Annotated[int, Field(
        description="Синхронизировать транзакции за период, дни",
        examples=[30])
    ] = 50
"""

