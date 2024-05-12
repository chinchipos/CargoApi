from typing import List

from sqlalchemy import select as sa_select

from src.database import models
from src.repositories.base import BaseRepository
from src.schemas.author import AuthorCreateSchema


class AuthorRepository(BaseRepository):

    async def get_author(self, author_id: str) -> models.Author:
        stmt = sa_select(models.Author).where(models.Author.id == author_id).limit(1)
        dataset = await self.session.scalars(stmt)
        author = dataset.first()
        return author

    async def get_authors(self) -> List[models.Author]:
        stmt = sa_select(models.Author).order_by(models.Author.last_name)
        dataset = await self.session.scalars(stmt)
        authors = dataset.all()
        return authors

    async def create_author(self, author: AuthorCreateSchema) -> models.Author:
        new_author = models.Author(**author.model_dump())
        self.session.add(new_author)
        await self.session.flush()
        await self.session.commit()
        new_author = await self.get_author(new_author.id)
        return new_author
