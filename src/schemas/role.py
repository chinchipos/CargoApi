from pydantic import BaseModel, ConfigDict


class RoleReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    title: str
    description: str
