from datetime import date
from typing import Optional, List, Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.base import BaseSchema
from src.schemas.car import CarReadSchema
from src.schemas.card_type import CardTypeReadSchema
from src.schemas.company import CompanyReadMinimumSchema
from src.schemas.driver import DriverReadSchema
from src.schemas.system import SystemReadMinimumSchema
from src.schemas.validators import EmptyStrToNone


class CardEditSchema(BaseSchema):

    is_active: Annotated[
        bool | None,
        Field(
            description="Признак активности",
            examples=[True])
    ] = None

    card_type_id: Annotated[
        EmptyStrToNone | None,
        Field(
            description="UUID типа карт",
            examples=["14318c56-296e-40ba-91ea-9760bbfcfb90"])
    ] = None

    company_id: Annotated[
        EmptyStrToNone | None,
        Field(
            description="UUID организации",
            examples=["20f06bf0-ae28-4f32-b2ca-f57796103a71"])
    ] = None

    belongs_to_car_id: Annotated[
        EmptyStrToNone | None,
        Field(
            description="UUID автомобиля",
            examples=["c83180ab-27b0-4686-9572-f7e2c9b13676"])
    ] = None

    belongs_to_driver_id: Annotated[
        EmptyStrToNone | None,
        Field(
            description="UUID водителя",
            examples=["065b3791-ca25-46a3-b407-481ef33a1a20"])
    ] = None


class CardCreateSchema(CardEditSchema):

    card_number: Annotated[
        str,
        Field(
            description="Номер карты",
            examples=["502980100000358664"])
    ]


class CardMinimumReadSchema(CardCreateSchema):

    id: Annotated[
        str,
        Field(
            description="UUID карты",
            examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])
    ]

    is_active: Annotated[
        bool,
        Field(
            description="Признак активности",
            examples=[True])
    ]

    belongs_to_car: Annotated[
        CarReadSchema | None,
        Field(description="Автомобиль")
    ] = None

    belongs_to_driver: Annotated[
        DriverReadSchema | None,
        Field(description="Водитель")
    ] = None


class CardReadSchema(CardMinimumReadSchema):

    date_last_use: Annotated[
        date | None,
        Field(
            description="Дата последнего использования",
            examples=[True])
    ] = None

    manual_lock: Annotated[
        bool,
        Field(
            description="Признак ручной блокировки",
            examples=[True])
    ]

    card_type: Annotated[
        CardTypeReadSchema,
        Field(description="Тип карты")
    ]

    systems: Annotated[
        List[SystemReadMinimumSchema],
        Field(description="Системы")
    ] = []


class BulkBindSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    card_numbers: Annotated[List[str], Field(description="Номера карт", examples=[["502980100000358664"]])]

    company_id: Annotated[
        Optional[EmptyStrToNone],
        Field(description="UUID организации", examples=["20f06bf0-ae28-4f32-b2ca-f57796103a71"])
    ] = None

    system_ids: Annotated[
        Optional[List[EmptyStrToNone]],
        Field(description="Список UUID поставщиков услуг", examples=["20f06bf0-ae28-4f32-b2ca-f57796103a71"])
    ] = None


class BulkUnbindSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    card_numbers: Annotated[
        Optional[List[str]], Field(description="Список номеров карт", examples=[["502980100000358664"]])
    ] = []
