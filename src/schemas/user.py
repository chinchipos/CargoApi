import uuid
from typing import Optional

from fastapi_users import models, schemas

from pydantic import EmailStr
from pydantic import BaseModel, ConfigDict

from src.schemas.role import RoleReadSchema


class NewUserReadSchema(schemas.BaseUser[uuid.UUID]):
    id: models.ID
    username: str
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    is_active: bool = True


class UserReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    is_active: bool = True
    role: Optional[RoleReadSchema]


class UserCreateSchema(schemas.BaseUserCreate):
    model_config = ConfigDict(from_attributes=True)

    username: str
    password: str
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    is_active: Optional[bool] = True
    role_id: str
    company_id: Optional[str] = None
    is_superuser: Optional[bool] = False
    is_verified: Optional[bool] = False


'''
class UserUpdate(schemas.BaseUserUpdate):
    password: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    is_verified: Optional[bool] = None
'''
