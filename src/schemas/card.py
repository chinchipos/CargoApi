from datetime import date
from typing import List, Annotated

from pydantic import Field

from src.schemas.balance import BalanceReadMinimumSchema
from src.schemas.base import BaseSchema
from src.schemas.car import CarReadMinimumSchema
from src.schemas.card_type import CardTypeReadSchema
from src.schemas.company import CompanyReadMinimumSchema
from src.schemas.driver import DriverReadMinimumSchema
from src.schemas.system import SystemReadMinimumSchema
from src.schemas.validators import EmptyStrToNone


class CardBindingMinimumSchemaForCard(BaseSchema):
    system: Annotated[SystemReadMinimumSchema | None, Field(description="Система")] = None
    balance: Annotated[BalanceReadMinimumSchema | None, Field(description="Баланс")] = None


pk_ = Annotated[str, Field(description="UUID карты", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]

card_number_ = Annotated[str | None, Field(description="Номер карты", examples=["502980100000358664"])]

is_active_ = Annotated[bool | None, Field(description="Признак активности", examples=[True])]

card_type_id_ = Annotated[
    EmptyStrToNone | None,
    Field(description="UUID типа карт", examples=["14318c56-296e-40ba-91ea-9760bbfcfb90"])
]

card_type_ = Annotated[CardTypeReadSchema, Field(description="Тип карты")]

company_id_ = Annotated[
    EmptyStrToNone | None,
    Field(description="UUID организации", examples=["20f06bf0-ae28-4f32-b2ca-f57796103a71"])
]

company_ = Annotated[CompanyReadMinimumSchema | None, Field(description="Организация")]

belongs_to_car_id_ = Annotated[
    EmptyStrToNone | None,
    Field(description="UUID автомобиля", examples=["c83180ab-27b0-4686-9572-f7e2c9b13676"])
]

belongs_to_car_ = Annotated[CarReadMinimumSchema | None, Field(description="Автомобиль")]

belongs_to_driver_id_ = Annotated[
    EmptyStrToNone | None,
    Field(description="UUID водителя", examples=["065b3791-ca25-46a3-b407-481ef33a1a20"])
]

belongs_to_driver_ = Annotated[DriverReadMinimumSchema | None, Field(description="Водитель")]

date_last_use_ = Annotated[date | None, Field(description="Дата последнего использования", examples=[True])]

manual_lock_ = Annotated[bool | None, Field(description="Признак ручной блокировки", examples=[True])]

systems_ = Annotated[List[SystemReadMinimumSchema], Field(description="Системы")]

card_numbers_ = Annotated[List[str], Field(description="Номера карт", examples=[["502980100000358664"]])]

system_ids_ = Annotated[
    List[EmptyStrToNone],
    Field(description="Список UUID поставщиков услуг", examples=["20f06bf0-ae28-4f32-b2ca-f57796103a71"])
]

card_bindings_ = Annotated[
    List[CardBindingMinimumSchemaForCard],
    Field(description="Привязка карты к системам и тарифам")
]


class CardEditSchema(BaseSchema):
    card_number: card_number_ = None
    is_active: is_active_ = None
    card_type_id: card_type_id_ = None
    company_id: company_id_ = None
    belongs_to_car_id: belongs_to_car_id_ = None
    belongs_to_driver_id: belongs_to_driver_id_ = None
    manual_lock: manual_lock_ = None


class CardCreateSchema(BaseSchema):
    card_number: card_number_
    is_active: is_active_ = None
    card_type_id: card_type_id_
    company_id: company_id_ = None
    belongs_to_car_id: belongs_to_car_id_ = None
    belongs_to_driver_id: belongs_to_driver_id_ = None


class CardMinimumReadSchema(BaseSchema):
    id: pk_
    is_active: is_active_
    card_number: card_number_


class CardReadSchema(BaseSchema):
    id: pk_
    is_active: is_active_
    card_number: card_number_
    card_type: card_type_ = None
    company: company_ = None
    belongs_to_car: belongs_to_car_ = None
    belongs_to_driver: belongs_to_driver_ = None
    date_last_use: date_last_use_ = None
    manual_lock: manual_lock_
    card_bindings: card_bindings_ = []


class BulkBindSchema(BaseSchema):
    card_numbers: card_numbers_
    company_id: company_id_ = None
    system_ids: system_ids_ = []


class BulkUnbindSchema(BaseSchema):
    card_numbers: card_numbers_ = []
