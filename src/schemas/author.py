from datetime import date
from pydantic import BaseModel, ConfigDict


class AuthorViewSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    first_name: str
    last_name: str
    date_birth: date
    biography: str


class AuthorCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    first_name: str
    last_name: str
    date_birth: date
    biography: str
