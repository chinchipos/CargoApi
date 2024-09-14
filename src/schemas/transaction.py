from datetime import datetime
from typing import Annotated

from pydantic import Field

from src.schemas.azs import AzsReadMinSchema
from src.schemas.base import BaseSchema
from src.schemas.card import CardMinimumReadSchema
from src.schemas.goods import OuterGoodsItemReadSchema
from src.schemas.system import SystemReadMinimumSchema
from src.schemas.tariff import TariffNewReadMinSchema
from src.schemas.validators import CompanyMinimumSchema
from src.utils.enums import TransactionType

id_ = Annotated[str, Field(description="UUID транзакции", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]

date_time_ = Annotated[
    datetime,
    Field(description="Время совершения (МСК)", examples=["2024-03-20 13:34:28"])
]

date_time_load_ = Annotated[
    datetime,
    Field(description="Время прогрузки в БД (МСК)", examples=["2024-03-20 17:19:03"])
]

transaction_type_ = Annotated[TransactionType, Field(description="Тип транзакции", examples=[True])]

system_ = Annotated[SystemReadMinimumSchema | None, Field(description="Поставщик услуг")]

card_ = Annotated[CardMinimumReadSchema | None, Field(description="Карта")]

company_ = Annotated[CompanyMinimumSchema | None, Field(description="Организация")]

azs_code_ = Annotated[str, Field(description="Код АЗС", examples=["АЗС № 07 (АБНС)"])]

outer_goods_ = Annotated[OuterGoodsItemReadSchema | None, Field(description="Товар/услуга")]

fuel_volume_ = Annotated[float, Field(description="Кол-во топлива, литры", examples=[80.0])]

price_ = Annotated[float, Field(description="Цена, руб", examples=[54.15])]

transaction_sum_ = Annotated[float, Field(description="Сумма транзакции, руб", examples=[4332.0])]

discount_sum_ = Annotated[float, Field(description="Размер скидки, руб", examples=[0.0])]

# tariff_ = Annotated[TariffMinimumReadSchema | None, Field(description="Тариф")]
tariff_new_ = Annotated[TariffNewReadMinSchema | None, Field(description="Тариф")]

fee_percent_ = Annotated[float, Field(description="Комиссия за обслуживание, %", examples=[0.5])]

fee_sum_ = Annotated[float, Field(description="Комиссия за обслуживание, руб", examples=[21.66])]

total_sum_ = Annotated[float, Field(description="Итоговая сумма, руб", examples=[4353.66])]

card_balance_ = Annotated[float, Field(description="Баланс карты после транзакции, руб", examples=[0.0])]

company_balance_ = Annotated[float, Field(description="Баланс организации после транзакции, руб", examples=[271866.35])]

comments_ = Annotated[str, Field(description="Комментарии", examples=[""])]


class TransactionReadSchema(BaseSchema):
    id: id_
    date_time: date_time_
    date_time_load: date_time_load_
    transaction_type: transaction_type_
    system: system_ = None
    card: card_ = None
    company: company_ = None
    azs_code: azs_code_
    azs: Annotated[AzsReadMinSchema | None, Field(description="АЗС")] = None
    outer_goods: outer_goods_ = None
    fuel_volume: fuel_volume_
    price: price_
    transaction_sum: transaction_sum_
    discount_sum: discount_sum_
    tariff_new: tariff_new_ = None
    fee_sum: fee_sum_
    total_sum: total_sum_
    company_balance: company_balance_
    comments: comments_
