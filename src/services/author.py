from typing import List

from src.database import models
from src.database.models import User
from src.repositories.author import AuthorRepository
from src.schemas.author import AuthorCreateSchema


class AuthorService:

    def __init__(self, repository: AuthorRepository, user: User) -> None:
        self.repository = repository
        self.user = user

    async def get_authors(self) -> List[models.Author]:
        authors = await self.repository.get_authors()
        return authors

    async def create_author(self, author: AuthorCreateSchema) -> models.Author:
        new_author = await self.repository.create_author(author)
        return new_author
