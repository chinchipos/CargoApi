import uuid
from typing import Optional, List, Annotated

from fastapi_users import models, schemas

from pydantic import EmailStr, Field
from pydantic import BaseModel, ConfigDict

from src.schemas.company import CompanyReadMinimumSchema
from src.schemas.role import RoleReadSchema
from src.schemas.validators import EmptyStrToNone


class NewUserReadSchema(schemas.BaseUser[uuid.UUID]):
    id: Annotated[models.ID, Field(description="UUID пользователя", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]
    username: Annotated[str, Field(description="Имя пользователя", examples=["user"])]
    first_name: Annotated[str, Field(description="Имя", examples=["Алексей"])]
    last_name: Annotated[str, Field(description="Фамилия", examples=["Гагарин"])]
    email: Annotated[EmailStr, Field(description="Email", examples=["user@cargonomica.com"])]
    phone: Annotated[str, Field(description="Телефон", examples=["+79332194370"])]
    is_active: Annotated[Optional[bool], Field(description="Признак активности", examples=[True])] = True


class UserReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Annotated[str, Field(description="UUID пользователя", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]
    username: Annotated[str, Field(description="Имя пользователя", examples=["user"])]
    first_name: Annotated[str, Field(description="Имя", examples=["Алексей"])]
    last_name: Annotated[str, Field(description="Фамилия", examples=["Гагарин"])]
    email: Annotated[EmailStr, Field(description="Email", examples=["user@cargonomica.com"])]
    phone: Annotated[str, Field(description="Телефон", examples=["+79332194370"])]
    is_active: Annotated[bool, Field(description="Признак активности", examples=[True])]
    role: Annotated[Optional[RoleReadSchema], Field(description="Роль")]


class UserCompanyReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Annotated[str, Field(description="UUID пользователя", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]
    username: Annotated[str, Field(description="Имя пользователя", examples=["user"])]
    first_name: Annotated[str, Field(description="Имя", examples=["Алексей"])]
    last_name: Annotated[str, Field(description="Фамилия", examples=["Гагарин"])]
    email: Annotated[EmailStr, Field(description="Email", examples=["user@cargonomica.com"])]
    phone: Annotated[str, Field(description="Телефон", examples=["+79332194370"])]
    is_active: Annotated[bool, Field(description="Признак активности", examples=[True])]
    role: Annotated[Optional[RoleReadSchema], Field(description="Роль")]
    company: Annotated[Optional[CompanyReadMinimumSchema], Field(description="Организация")]


class UserCargoReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Annotated[str, Field(description="UUID пользователя", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]
    username: Annotated[str, Field(description="Имя пользователя", examples=["user"])]
    first_name: Annotated[str, Field(description="Имя", examples=["Алексей"])]
    last_name: Annotated[str, Field(description="Фамилия", examples=["Гагарин"])]
    email: Annotated[EmailStr, Field(description="Email", examples=["user@cargonomica.com"])]
    phone: Annotated[str, Field(description="Телефон", examples=["+79332194370"])]
    is_active: Annotated[bool, Field(description="Признак активности", examples=[True])]
    role: Annotated[Optional[RoleReadSchema], Field(description="Роль")]
    managed_companies: Annotated[List[CompanyReadMinimumSchema], Field(description="Администрируемые организации")]


class UserCreateSchema(schemas.BaseUserCreate):
    model_config = ConfigDict(from_attributes=True)
    email: Annotated[EmailStr, Field(description="Email", examples=["user@cargonomica.com"])]
    password: Annotated[str, Field(description="Пароль", examples=["Xuu76mn66%$"])]
    first_name: Annotated[str, Field(description="Имя", examples=["Алексей"])]
    last_name: Annotated[str, Field(description="Фамилия", examples=["Гагарин"])]
    username: Annotated[str, Field(description="Имя пользователя", examples=["user"])]
    phone: Annotated[str, Field(description="Телефон", examples=["+79332194370"])]
    is_active: Annotated[Optional[bool], Field(description="Признак активности", examples=[True])] = True
    is_superuser: Annotated[bool, Field(deprecated=True)] = False
    is_verified: Annotated[bool, Field(deprecated=True)] = False
    role_id: Annotated[str, Field(description="ID роли", examples=["059d01d6-c023-47a2-974f-afedd2ce4bfd"])]
    company_id: Annotated[
        Optional[EmptyStrToNone],
        Field(description="ID организации", examples=["20f06bf0-ae28-4f32-b2ca-f57796103a71"])
    ] = None


class UserEditSchema(schemas.BaseUserCreate):
    model_config = ConfigDict(from_attributes=True)
    username: Annotated[Optional[str], Field(description="Имя пользователя", examples=["user"])] = None
    password: Annotated[Optional[str], Field(description="Пароль", examples=["Xuu76mn66%$"])] = None
    first_name: Annotated[Optional[str], Field(description="Имя", examples=["Алексей"])] = None
    last_name: Annotated[Optional[str], Field(description="Фамилия", examples=["Гагарин"])] = None
    phone: Annotated[Optional[str], Field(description="Телефон", examples=["+79332194370"])] = None
    is_active: Annotated[Optional[bool], Field(description="Признак активности", examples=[True])] = None

    role_id: Annotated[
        Optional[str],
        Field(description="ID роли", examples=["059d01d6-c023-47a2-974f-afedd2ce4bfd"])
    ] = None
    
    company_id: Annotated[
        Optional[str],
        Field(description="ID организации", examples=["20f06bf0-ae28-4f32-b2ca-f57796103a71"])
    ] = None


class UserImpersonatedSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Annotated[str, Field(description="UUID пользователя", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]
    access_token: Annotated[str, Field(
        description="Access Token",
        examples=[(
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwNjViMzc5MS1jYTI1LTQ2YTMtYjQwNy00ODFlZjMzYTFhMjAiLCJhdWQ"
            "iOlsiZmFzdGFwaS11c2VyczphdXRoIl0sImV4cCI6MTcxOTI5MzE1MX0.Dy3inizhElunx5k5A_KbXYm-zKTFWzGzBrBrRq3v9NA"
        )]
    )]
    token_type: Annotated[str, Field(description="Тип токена", examples=["bearer"])]
    username: Annotated[str, Field(description="Имя пользователя", examples=["user"])]
    first_name: Annotated[str, Field(description="Имя", examples=["Алексей"])]
    last_name: Annotated[str, Field(description="Фамилия", examples=["Гагарин"])]
    email: Annotated[EmailStr, Field(description="Email", examples=["user@cargonomica.com"])]
    is_active: Annotated[bool, Field(description="Признак активности", examples=[True])]
    role: Annotated[RoleReadSchema, Field(description="Роль")]
