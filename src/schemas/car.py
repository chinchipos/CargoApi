from typing import List, Set, Optional, Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.company import CompanyReadMinimumSchema
from src.schemas.driver import DriverReadMinimumSchema
from src.schemas.validators import EmptyStrToNone


class CarReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Annotated[str, Field(description="UUID автомобиля", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]
    model: Annotated[str, Field(description="Марка/модель", examples=["Камаз"])]
    reg_number: Annotated[str, Field(description="Государственный регистрационный номер", examples=["Н314УР77"])]
    company: Annotated[Optional[CompanyReadMinimumSchema], Field(description="Организация")] = None
    drivers: Annotated[Optional[List[DriverReadMinimumSchema]], Field(description="Список водителей")] = []


class CarCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model: Annotated[str, Field(description="Марка/модель", examples=["Камаз"])]
    reg_number: Annotated[str, Field(description="Государственный регистрационный номер", examples=["Н314УР77"])]

    company_id: Annotated[EmptyStrToNone, Field(
        description="UUID организации",
        examples=["20f06bf0-ae28-4f32-b2ca-f57796103a71"])
    ]

    driver_ids: Annotated[Optional[Set[EmptyStrToNone]], Field(
        description="Список UUID водителей",
        examples=[["065b3791-ca25-46a3-b407-481ef33a1a20"]])
    ] = set()


class CarEditSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model: Annotated[str, Field(description="Марка/модель", examples=["Камаз"])]
    reg_number: Annotated[str, Field(description="Государственный регистрационный номер", examples=["Н314УР77"])]
    driver_ids: Annotated[Optional[Set[EmptyStrToNone]], Field(
        description="Список UUID водителей",
        examples=[["065b3791-ca25-46a3-b407-481ef33a1a20"]])
    ] = set()
