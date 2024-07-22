from typing import List, Dict, Any, Annotated

from pydantic import Field

from src.schemas.base import BaseSchema

any_ = List[Dict[str, Any]]

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


class DBInitSchema(BaseSchema):
    service_token: service_token_
    superuser_password: superuser_password_


class DBInitialSyncSchema(BaseSchema):
    service_token: service_token_
    systems: any_
    tariffs: any_
    companies: any_
    cars: any_
    cards: any_
    goods: any_
    transactions: any_
    users: any_


class DBRegularSyncSchema(BaseSchema):
    service_token: str
    companies: any_
