from typing import Optional

from pydantic import BaseModel, ConfigDict

from src.schemas.company import CompanyReadMinimumSchema


class DriverReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    first_name: str
    last_name: str
    company: Optional[CompanyReadMinimumSchema] = None


class DriverReadMinimumSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    first_name: str
    last_name: str
