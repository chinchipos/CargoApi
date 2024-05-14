from typing import Optional

from pydantic import BaseModel, ConfigDict


class SystemReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    full_name: str
    short_name: str
    contract_num: str
    login: str
    transaction_days: int
    balance: float
    transactions_sync_dt: Optional[str]
    cards_sync_dt: Optional[str]
    balance_sync_dt: Optional[str]
    cards_amount: int


class SystemCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    full_name: str
    short_name: str
    contract_num: str
    login: str
    password: str
    transaction_days: int = 50


class SystemEditSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    full_name: Optional[str] = None
    short_name: Optional[str] = None
    contract_num: Optional[str] = None
    login: Optional[str] = None
    password: Optional[str] = None
    transaction_days: Optional[int] = None


class SystemDeleteSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
