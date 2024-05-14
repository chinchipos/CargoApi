from pydantic import BaseModel, ConfigDict


class SuccessSchema(BaseModel):
    success: bool = True


class ModelIDSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
