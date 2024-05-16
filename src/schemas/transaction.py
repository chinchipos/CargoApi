from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from src.schemas.card import CardMinimumReadSchema
from src.schemas.company import CompanyReadMinimumSchema
from src.schemas.goods import OuterGoodsReadSchema
from src.schemas.system import SystemReadMinimumSchema
from src.schemas.tariff import TariffMinimumReadSchema


class TransactionReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    date_time: datetime
    date_time_load: datetime
    is_debit: bool
    system: Optional[SystemReadMinimumSchema] = None
    card: Optional[CardMinimumReadSchema] = None
    company: Optional[CompanyReadMinimumSchema] = None
    azs_code: str
    azs_address: str
    outer_goods: Optional[OuterGoodsReadSchema] = None
    fuel_volume: float
    price: float
    transaction_sum: float
    discount_sum: float
    tariff: Optional[TariffMinimumReadSchema] = None
    fee_percent: float
    fee_sum: float
    total_sum: float
    card_balance: float
    company_balance: float
    comments: str
