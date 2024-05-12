from datetime import date
from pydantic import BaseModel, ConfigDict
from src.schemas.author import AuthorViewSchema


class BookViewSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    annotation: str
    date_publishing: date
    author: AuthorViewSchema

class BookCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    annotation: str
    date_publishing: date
    author_id: str