from pydantic import BaseModel, ConfigDict


class CarReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    model: str
    reg_number: str