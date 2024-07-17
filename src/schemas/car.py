from typing import List, Annotated

from pydantic import Field

from src.schemas.base import BaseSchema
from src.schemas.company import CompanyReadMinimumSchema
from src.schemas.driver import DriverReadMinimumSchema
from src.schemas.validators import EmptyStrToNone

id_ = Annotated[str, Field(description="UUID автомобиля", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]

model_ = Annotated[str, Field(description="Марка/модель", examples=["Камаз"])]

reg_number_ = Annotated[str, Field(description="Государственный регистрационный номер", examples=["Н314УР77"])]

company_id_ = Annotated[
    EmptyStrToNone,
    Field(description="UUID организации", examples=["20f06bf0-ae28-4f32-b2ca-f57796103a71"])
]

company_ = Annotated[CompanyReadMinimumSchema | None, Field(description="Организация")]

driver_ids_ = Annotated[
    List[EmptyStrToNone],
    Field(description="Список UUID водителей", examples=[["065b3791-ca25-46a3-b407-481ef33a1a20"]])
]

drivers_ = Annotated[List[DriverReadMinimumSchema], Field(description="Список водителей")]


class CarReadMinimumSchema(BaseSchema):
    id: id_
    model: model_
    reg_number: reg_number_

class CarReadSchema(BaseSchema):
    id: id_
    model: model_
    reg_number: reg_number_
    company: company_ = None
    drivers: drivers_ = []


class CarCreateSchema(BaseSchema):
    model: model_
    reg_number: reg_number_
    company_id: company_id_
    driver_ids: driver_ids_ = []


class CarEditSchema(BaseSchema):
    model: model_ = None
    reg_number: reg_number_ = None
    driver_ids: driver_ids_ = []
