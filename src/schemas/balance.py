from datetime import date

from pydantic import Field

from src.schemas.base import BaseSchema
from src.schemas.contract import ContractReadSchema
from src.schemas.system import SystemReadMinimumSchema
from src.utils import enums

from typing import Annotated, List


class BalanceEditSchema(BaseSchema):

    min_balance: Annotated[
        float | None,
        Field(
            description="Постоянный овердрафт (минимальный баланс), руб",
            examples=[10000.0])
    ] = None

    min_balance_on_period: Annotated[
        float | None,
        Field(
            description="Временный овердрафт (минимальный баланс), руб",
            examples=[30000.0])
    ] = None

    min_balance_period_end_date: Annotated[
        date | None,
        Field(
            description="Дата прекращения действия временного овердрафта",
            examples=["2023-05-17"])
    ] = None


class BalanceCreateSchema(BalanceEditSchema):

    scheme: Annotated[
        enums.ContractScheme | None,
        Field(
            description="Договорная схема [Агентская, Перекупная]",
            examples=["Агентская"])
    ] = None


class BalanceReadMinimumSchema(BalanceEditSchema):

    id: Annotated[
        str,
        Field(
            description="UUID договора",
            examples=["75325199-ac93-4733-becb-de2e89e85202"])
    ]

    balance: Annotated[
        float | None,
        Field(
            description="Номер договора (не более 20 символов)",
            examples=["2024/А179"])
    ] = None


class BalanceReadSchema(BalanceReadMinimumSchema, BalanceCreateSchema):

    systems: Annotated[
        List[SystemReadMinimumSchema] | None,
        Field(description="Поставщики услуг")
    ] = []
