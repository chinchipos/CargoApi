from typing import Optional, Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.company import CompanyReadMinimumSchema


class DriverReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Annotated[str, Field(description="UUID водителя", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]
    first_name: Annotated[str, Field(description="Имя", examples=["Алексей"])]
    last_name: Annotated[str, Field(description="Фамилия", examples=["Гагарин"])]
    company: Annotated[Optional[CompanyReadMinimumSchema], Field(description="Организация")] = None


class DriverReadMinimumSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Annotated[str, Field(description="UUID водителя", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]
    first_name: Annotated[str, Field(description="Имя", examples=["Алексей"])]
    last_name: Annotated[str, Field(description="Фамилия", examples=["Гагарин"])]
