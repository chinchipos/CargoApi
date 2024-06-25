from datetime import datetime
from typing import Optional, Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.card import CardMinimumReadSchema
from src.schemas.company import CompanyReadMinimumSchema
from src.schemas.goods import OuterGoodsReadSchema
from src.schemas.system import SystemReadMinimumSchema
from src.schemas.tariff import TariffMinimumReadSchema
from src.schemas.validators import DateTimeNormalized


class TransactionReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Annotated[str, Field(description="UUID транзакции", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]
    date_time: Annotated[DateTimeNormalized, Field(
        description="Время совершения (МСК)",
        examples=["2024-03-20 13:34:28"])
    ]
    date_time_load: Annotated[DateTimeNormalized, Field(
        description="Время прогрузки в БД (МСК)",
        examples=["2024-03-20 17:19:03"])
    ]
    is_debit: Annotated[bool, Field(description="Операция дебетования/кредитования", examples=[True])]
    system: Annotated[Optional[SystemReadMinimumSchema], Field(description="Поставщик услуг")] = None
    card: Annotated[Optional[CardMinimumReadSchema], Field(description="Карта")] = None
    company: Annotated[Optional[CompanyReadMinimumSchema], Field(description="Организация")] = None
    azs_code: Annotated[str, Field(description="Код АЗС", examples=["АЗС № 07 (АБНС)"])]
    azs_address: Annotated[str, Field(
        description="Адрес АЗС",
        examples=["Россия, Свердловская область, Заречный, Р351, 46 км, справа, с. Мезенское"])
    ]
    outer_goods: Annotated[Optional[OuterGoodsReadSchema], Field(description="Товар/услуга")] = None
    fuel_volume: Annotated[float, Field(description="Кол-во топлива, литры", examples=[80.0])]
    price: Annotated[float, Field(description="Цена, руб", examples=[54.15])]
    transaction_sum: Annotated[float, Field(description="Сумма транзакции, руб", examples=[4332.0])]
    discount_sum: Annotated[float, Field(description="Размер скидки, руб", examples=[0.0])]
    tariff: Annotated[Optional[TariffMinimumReadSchema], Field(description="Тариф")] = None
    fee_percent: Annotated[float, Field(description="Комиссия за обслуживание, %", examples=[0.5])]
    fee_sum: Annotated[float, Field(description="Комиссия за обслуживание, руб", examples=[21.66])]
    total_sum: Annotated[float, Field(description="Итоговая сумма, руб", examples=[4353.66])]
    card_balance: Annotated[float, Field(description="Баланс карты после транзакции, руб", examples=[0.0])]
    company_balance: Annotated[float, Field(description="Баланс организации после транзакции, руб", examples=[271866.35])]
    comments: Annotated[str, Field(description="Комментарии", examples=[""])]
