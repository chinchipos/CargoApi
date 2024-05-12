from pydantic import BaseModel


class SuccessSchema(BaseModel):
    success: bool = True
