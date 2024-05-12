from typing import List

from sqlalchemy import select as sa_select
from sqlalchemy.orm import joinedload

from src.database import models
from src.repositories.base import BaseRepository
from src.schemas.book import BookCreateSchema


class BookRepository(BaseRepository):

    async def get_book(self, book_id: str) -> models.Book:
        stmt = (
            sa_select(models.Book)
            .options(joinedload(models.Book.author))
            .where(models.Book.id == book_id)
            .limit(1)
        )
        dataset = await self.session.scalars(stmt)
        book = dataset.first()
        return book

    async def get_books(self) -> List[models.Book]:
        stmt = (
            sa_select(models.Book)
            .options(joinedload(models.Book.author))
            .order_by(models.Book.title)
        )
        dataset = await self.session.scalars(stmt)
        books = dataset.all()
        return books

    async def create_book(self, book: BookCreateSchema) -> models.Book:
        new_book = models.Book(**book.model_dump())
        self.session.add(new_book)
        await self.session.flush()
        await self.session.commit()
        new_book = await self.get_book(new_book.id)
        return new_book
