from datetime import date
from typing import Optional, List

from pydantic import BaseModel, ConfigDict

from src.schemas.role import RoleReadSchema


class CompanyTariffSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    fee_percent: float


class CompanyUserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    first_name: str
    last_name: str
    role: RoleReadSchema


class CompanyReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    inn: str
    personal_account: Optional[str] = None
    contacts: Optional[str] = None
    date_add: Optional[date] = None
    balance: Optional[float] = None
    min_balance: Optional[float] = None
    min_balance_on_period: Optional[float] = None
    min_balance_period_end_date: Optional[date] = None
    cards_amount: Optional[int] = None
    tariff: Optional[CompanyTariffSchema] = None
    users: Optional[List[CompanyUserSchema]] = None


class CompanyReadMinimumSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    inn: str


class CompanyEditSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: Optional[str] = None
    inn: Optional[str] = None
    tariff_id: Optional[str] = None
    contacts: Optional[str] = None
    min_balance: Optional[float] = None
    min_balance_on_period: Optional[float] = None
    min_balance_period_end_date: Optional[date] = None
