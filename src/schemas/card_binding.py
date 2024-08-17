from typing import Annotated

from pydantic import Field

from src.schemas.balance import BalanceReadMinimumSchema, BalanceReadSchema
from src.schemas.base import BaseSchema
from src.schemas.card import CardMinimumReadSchema, CardReadSchema
from src.schemas.system import SystemReadMinimumSchema, SystemReadSchema

id_ = Annotated[str, Field(description="UUID поставщика услуг", examples=["68425199-ac93-4733-becb-de2e89e85303"])]

card_minimum_ = Annotated[CardMinimumReadSchema | None, Field(description="Карта")]

card_ = Annotated[CardReadSchema | None, Field(description="Карта")]

system_minimum_ = Annotated[SystemReadMinimumSchema | None, Field(description="Система")]

system_ = Annotated[SystemReadSchema | None, Field(description="Система")]

balance_minimum_ = Annotated[BalanceReadMinimumSchema | None, Field(description="Баланс")]

balance_ = Annotated[BalanceReadSchema | None, Field(description="Баланс")]


class CardBindingMinimumSchemaForCard(BaseSchema):
    id: id_
    system: system_minimum_ = None
    balance: balance_minimum_ = None
