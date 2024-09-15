from datetime import date
from typing import Annotated, List

from pydantic import Field

from src.schemas.base import BaseSchema
from src.schemas.system import SystemReadMinimumSchema
from src.utils.enums import ContractScheme

system_id_ = Annotated[
    str,
    Field(description="UUID поставщика услуг", examples=["68425199-ac93-4733-becb-de2e89e85303"])]


id_ = Annotated[str, Field(description="UUID договора", examples=["75325199-ac93-4733-becb-de2e89e85202"])]

scheme_ = Annotated[
    ContractScheme,
    Field(description="Договорная схема [Агентская, Перекупная]", examples=["Агентская"])
]

balance_ = Annotated[float | None, Field(description="Номер договора (не более 20 символов)", examples=["2024/А179"])]

min_balance_ = Annotated[
    float | None,
    Field(description="Постоянный овердрафт (минимальный баланс), руб", examples=[10000.0])
]

min_balance_period_ = Annotated[
    float | None,
    Field(description="Временный овердрафт (минимальный баланс), руб", examples=[30000.0])
]

min_balance_period_end_date_ = Annotated[
    date | None,
    Field(description="Дата прекращения действия временного овердрафта", examples=["2023-05-17"])
]

systems_ = Annotated[List[SystemReadMinimumSchema], Field(description="Системы")]


class BalanceReadMinimumSchema(BaseSchema):
    id: id_
    scheme: scheme_


class BalanceReadSchema(BaseSchema):
    id: id_
    scheme: scheme_
    balance: balance_
    systems: systems_ = []
