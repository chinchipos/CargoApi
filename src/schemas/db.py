from typing import List, Dict, Any

from pydantic import BaseModel, Field


class DBSyncSchema(BaseModel):
    systems: List[dict]
    tariffs: List[dict]
    companies: List[dict]
    cars: List[dict]
    cards: List[dict]
    goods: List[dict]
    transactions: List[dict]


class DBInitSchema(BaseModel):
    service_token: str = Field(
        description="Сервисный токен (прописан в конфигурационном файле .env)",
        examples=["8954fc0196724b9ea538ef5e7d2f6d45"]
    )
    superuser_password: str = Field(
        description="Пароль создаваемого суперпользователя (логин - cargo)",
        examples=["X0ttR52zz_82"]
    )


class DBInitialSyncSchema(BaseModel):
    service_token: str = Field(
        description="Сервисный токен (прописан в конфигурационном файле .env)",
        examples=["8954fc0196724b9ea538ef5e7d2f6d45"]
    )
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
