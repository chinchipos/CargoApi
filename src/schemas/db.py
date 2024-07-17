from typing import List, Dict, Any, Annotated

from pydantic import Field

from src.schemas.base import BaseSchema

systems_ = List[Dict[str, Any]]

tariffs_ = List[Dict[str, Any]]

companies_ = List[Dict[str, Any]]

cars_ = List[Dict[str, Any]]

cards_ = List[Dict[str, Any]]

goods_ = List[Dict[str, Any]]

transactions_ = List[Dict[str, Any]]

service_token_ = Annotated[
    str,
    Field(description="Сервисный токен (прописан в конфигурационном файле .env)",
          examples=["8954fc0196724b9ea538ef5e7d2f6d45"])
]

superuser_password_ = Annotated[
    str,
    Field(description="Пароль создаваемого суперпользователя (логин - cargo)",
          examples=["X0ttR52zz_82"])
]


class DBSyncSchema(BaseSchema):
    systems: systems_
    tariffs: tariffs_
    companies: companies_
    cars: cars_
    cards: cards_
    goods: goods_
    transactions: transactions_


class DBInitSchema(BaseSchema):
    service_token: service_token_
    superuser_password: superuser_password_


class DBInitialSyncSchema(BaseSchema):
    service_token: service_token_
    systems: systems_
    tariffs: tariffs_
    companies: companies_
    cars: cars_
    cards: cards_
    goods: goods_
    transactions: transactions_


class DBRegularSyncSchema(BaseSchema):
    service_token: str
    companies: companies_
