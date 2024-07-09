from pydantic import Field

from src.schemas.base import BaseSchema
from src.schemas.system import SystemReadMinimumSchema
from src.schemas.tariff import TariffMinimumReadSchema
from src.utils import enums

from typing import Annotated


class ContractBaseSchema(BaseSchema):

    number: Annotated[
        str,
        Field(
            description="Номер договора (не более 20 символов)",
            examples=["2024/А179"],
            min_length=1,
            max_length=20)
    ]


class ContractEditSchema(ContractBaseSchema):

    tariff_id: Annotated[
        str,
        Field(
            description="UUID тарифа",
            examples=["75325199-ac93-4733-becb-de2e89e85202"])
    ]


class ContractCreateSchema(ContractEditSchema, ContractBaseSchema):

    balance_id: Annotated[
        str,
        Field(
            description="UUID баланса",
            examples=["28bc5199-ac93-4733-becb-de2e89e85303"])
    ]

    system_id: Annotated[
        str,
        Field(
            description="UUID поставщика услуг",
            examples=["33bc5199-ac93-4733-becb-de2e89e85417"])
    ]


class ContractReadSchema(ContractBaseSchema):

    id: Annotated[
        str,
        Field(
            description="UUID договора",
            examples=["75325199-ac93-4733-becb-de2e89e85202"])
    ]

    tariff: Annotated[
        TariffMinimumReadSchema,
        Field(description="Тариф")
    ]

    system: Annotated[
        SystemReadMinimumSchema,
        Field(description="Поставщик услуг")
    ]

    cards_amount: Annotated[
        int,
        Field(
            description="Количество карт",
            examples=[350])
    ] = 0
