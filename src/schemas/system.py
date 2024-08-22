from typing import Annotated

from pydantic import Field

from src.schemas.base import BaseSchema
from src.schemas.validators import DateTimeNormalized

id_ = Annotated[str, Field(description="UUID поставщика услуг", examples=["68425199-ac93-4733-becb-de2e89e85303"])]

full_name_ = Annotated[str | None, Field(description="Полное наименование", examples=["Роснефть"])]

balance_ = Annotated[float, Field(description="Баланс, руб", examples=[59327.98])]

transactions_sync_dt_ = Annotated[
    DateTimeNormalized | None,
    Field(description="Время последней успешной синхронизации транзакции", examples=["2024-06-22 13:30:45"])]

cards_sync_dt_ = Annotated[
    DateTimeNormalized | None,
    Field(description="Время последней успешной синхронизации карт", examples=["2024-06-22 13:30:45"])]

balance_sync_dt_ = Annotated[
    DateTimeNormalized | None,
    Field(description="Время последней успешной синхронизации баланса", examples=["2024-06-22 13:30:45"])]

cards_amount_total_ = Annotated[int, Field(description="Общее кол-во карт этого поставщика услуг", examples=[750])]

cards_amount_in_use_ = Annotated[
    int,
    Field(description="Кол-во используемых карт этого поставщика услуг", examples=[630])]

cards_amount_free_ = Annotated[
    int,
    Field(description="Кол-во неиспользуемых карт этого поставщика услуг", examples=[120])]

transaction_days_ = Annotated[
    int | None,
    Field(description="Синхронизировать транзакции за период, дни (0 < x <= 50)", examples=[30], ge=0, le=50)]

card_icon_url_ = Annotated[str | None, Field(description="Ссылка на иконку карты")]

limits_on_ = Annotated[bool, Field(description="В системе доступен функционал работы с лимитами")]


class SystemEditSchema(BaseSchema):
    full_name: full_name_ = None
    transaction_days: transaction_days_ = None


class SystemReadMinimumSchema(BaseSchema):
    id: id_
    full_name: full_name_


class SystemReadSchema(BaseSchema):
    id: id_
    full_name: full_name_
    balance: balance_
    transaction_days: transaction_days_
    transactions_sync_dt: transactions_sync_dt_
    cards_sync_dt: cards_sync_dt_
    balance_sync_dt: balance_sync_dt_
    cards_amount_total: cards_amount_total_
    cards_amount_in_use: cards_amount_in_use_
    cards_amount_free: cards_amount_free_
    card_icon_url: card_icon_url_


"""
class SystemCreateSchema(BaseSchema):
    full_name: Annotated[str, Field(description="Полное наименование", examples=["Роснефть"])]
    short_name: Annotated[str, Field(description="Сокращенное наименование", examples=["РН"])]
    transaction_days: Annotated[int, Field(
        description="Синхронизировать транзакции за период, дни",
        examples=[30])
    ] = 50
"""
