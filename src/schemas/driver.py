from typing import Optional, Annotated

from pydantic import Field

from src.schemas.base import BaseSchema
from src.schemas.company import CompanyReadMinimumSchema

id_ = Annotated[str, Field(description="UUID водителя", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]

first_name_ = Annotated[str, Field(description="Имя", examples=["Алексей"])]

last_name_ = Annotated[str, Field(description="Фамилия", examples=["Гагарин"])]

company_ = Annotated[Optional[CompanyReadMinimumSchema], Field(description="Организация")]


class DriverReadSchema(BaseSchema):
    id: id_
    first_name: first_name_
    last_name: last_name_
    company: company_ = None


class DriverReadMinimumSchema(BaseSchema):
    id: id_
    first_name: first_name_
    last_name: last_name_
