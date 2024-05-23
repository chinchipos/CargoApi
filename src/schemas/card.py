from datetime import date
from typing import Optional, List

from pydantic import BaseModel, ConfigDict

from src.schemas.car import CarReadSchema
from src.schemas.card_type import CardTypeReadSchema
from src.schemas.company import CompanyReadMinimumSchema
from src.schemas.driver import DriverReadSchema
from src.schemas.system import SystemReadMinimumSchema
from src.schemas.validators import EmptyStrToNone


class CardReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    card_number: str
    is_active: bool
    date_last_use: Optional[date] = None
    manual_lock: bool
    card_type: CardTypeReadSchema
    systems: List[SystemReadMinimumSchema] = []
    company: Optional[CompanyReadMinimumSchema] = None
    belongs_to_car: Optional[CarReadSchema] = None
    belongs_to_driver: Optional[DriverReadSchema] = None


class CardMinimumReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    card_number: str
    belongs_to_car: Optional[CarReadSchema] = None
    belongs_to_driver: Optional[DriverReadSchema] = None


class CardCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    card_number: str
    is_active: bool
    card_type_id: str
    company_id: Optional[str] = None
    belongs_to_car_id: Optional[EmptyStrToNone] = None
    belongs_to_driver_id: Optional[EmptyStrToNone] = None


class CardEditSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    is_active: Optional[bool] = None
    card_type_id: Optional[EmptyStrToNone] = None
    company_id: Optional[EmptyStrToNone] = None
    belongs_to_car_id: Optional[EmptyStrToNone] = None
    belongs_to_driver_id: Optional[EmptyStrToNone] = None
