from typing import List, Set, Optional

from pydantic import BaseModel, ConfigDict

from src.schemas.company import CompanyReadMinimumSchema
from src.schemas.driver import DriverReadMinimumSchema


class CarReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    model: str
    reg_number: str
    company: CompanyReadMinimumSchema
    drivers: Optional[List[DriverReadMinimumSchema]] = []


class CarCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model: str
    reg_number: str
    company_id: str
    driver_ids: Optional[Set[str]] = set()


class CarEditSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model: str
    reg_number: str
    driver_ids: Optional[Set[str]] = set()
