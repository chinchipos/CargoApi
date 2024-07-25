import uuid
from typing import List, Annotated

from fastapi_users import models as fastapi_models, schemas as fastapi_schemas
from pydantic import EmailStr, Field

from src.schemas.base import BaseSchema
from src.schemas.company import CompanyReadMinimumSchema
from src.schemas.role import RoleReadSchema
from src.schemas.validators import EmptyStrToNone

id_uuid_ = Annotated[
    fastapi_models.ID,
    Field(description="UUID пользователя", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])
]

id_str_ = Annotated[str, Field(description="UUID пользователя", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]

username_ = Annotated[str | None, Field(description="Имя пользователя", examples=["user"])]

first_name_ = Annotated[str | None, Field(description="Имя", examples=["Алексей"])]

last_name_ = Annotated[str | None, Field(description="Фамилия", examples=["Гагарин"])]

email_ = Annotated[EmailStr, Field(description="Email", examples=["user@cargonomica.com"])]

password_ = Annotated[str | None, Field(description="Пароль", examples=["Xuu76mn66"])]

phone_ = Annotated[str | None, Field(description="Телефон", examples=["+79332194370"])]

is_active_ = Annotated[bool | None, Field(description="Признак активности", examples=[True])]

role_id_ = Annotated[str | None, Field(description="ID роли", examples=["059d01d6-c023-47a2-974f-afedd2ce4bfd"])]

role_ = Annotated[RoleReadSchema | None, Field(description="Роль")]

company_id_ = Annotated[
    EmptyStrToNone | None,
    Field(description="ID организации", examples=["20f06bf0-ae28-4f32-b2ca-f57796103a71"])
]

company_ = Annotated[CompanyReadMinimumSchema | None, Field(description="Организация")]

managed_companies_ = Annotated[List[CompanyReadMinimumSchema], Field(description="Администрируемые организации")]

access_token_ = Annotated[
    str,
    Field(description="Access Token",
          examples=[(
              "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwNjViMzc5MS1jYTI1LTQ2YTMtYjQwNy00ODFlZjMzYTFhMjAiLCJhdWQ"
              "iOlsiZmFzdGFwaS11c2VyczphdXRoIl0sImV4cCI6MTcxOTI5MzE1MX0.Dy3inizhElunx5k5A_KbXYm-zKTFWzGzBrBrRq3v9NA")])
]

token_type_ = Annotated[str, Field(description="Тип токена", examples=["bearer"])]


class NewUserReadSchema(fastapi_schemas.BaseUser[uuid.UUID]):
    id: id_uuid_
    username: username_
    first_name: first_name_
    last_name: last_name_
    email: email_
    phone: phone_
    is_active: is_active_ = True


class UserReadSchema(BaseSchema):
    id: id_str_
    username: username_
    first_name: first_name_
    last_name: last_name_
    email: email_
    phone: phone_
    is_active: is_active_
    role: role_ = None
    company: company_ = None


class UserCompanyReadSchema(BaseSchema):
    id: id_str_
    username: username_
    first_name: first_name_
    last_name: last_name_
    email: email_
    phone: phone_
    is_active: is_active_
    role: role_ = None
    company: company_ = None


class UserCargoReadSchema(BaseSchema):
    id: id_str_
    username: username_
    first_name: first_name_
    last_name: last_name_
    email: email_
    phone: phone_
    is_active: is_active_
    role: role_
    managed_companies: managed_companies_ = []


class UserCreateSchema(fastapi_schemas.BaseUserCreate):
    email: email_
    password: Annotated[str, Field(description="Пароль", examples=["Xuu76mn66%$"])]
    first_name: first_name_
    last_name: last_name_
    username: username_
    phone: phone_
    is_active: is_active_ = True
    is_superuser: Annotated[bool, Field(deprecated=True)] = False
    is_verified: Annotated[bool, Field(deprecated=True)] = False
    role_id: role_id_
    company_id: company_id_ = None


class UserEditSchema(fastapi_schemas.BaseUserCreate):
    username: username_ = None
    password: password_ = None
    first_name: first_name_ = None
    last_name: last_name_ = None
    phone: phone_ = None
    is_active: is_active_ = None
    role_id: role_id_ = None
    company_id: company_id_ = None


class UserImpersonatedSchema(BaseSchema):
    id: id_str_
    access_token: access_token_
    token_type: token_type_
    username: username_
    first_name: first_name_
    last_name: last_name_
    email: email_
    is_active: is_active_
    role: role_
