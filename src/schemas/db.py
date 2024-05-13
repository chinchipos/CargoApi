from typing import List, Dict, Any

from pydantic import BaseModel


class DBSyncSchema(BaseModel):
    systems: List[dict]
    tariffs: List[dict]
    companies: List[dict]
    cars: List[dict]
    cards: List[dict]
    goods: List[dict]
    transactions: List[dict]


class DBInitSchema(BaseModel):
    service_token: str
    superuser_password: str


class DBInitialSyncSchema(BaseModel):
    service_token: str
    systems: list[Dict[str, Any]]
    tariffs: list[Dict[str, Any]]
    companies: list[Dict[str, Any]]
    cars: list[Dict[str, Any]]
    cards: list[Dict[str, Any]]
    goods: list[Dict[str, Any]]
    transactions: list[Dict[str, Any]]


class DBRegularSyncSchema(BaseModel):
    service_token: str
    companies: list[Dict[str, Any]]
