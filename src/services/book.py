from typing import List

from src.database import models
from src.repositories.book import BookRepository
from src.schemas.book import BookCreateSchema


class BookService:

    def __init__(self, repository: BookRepository) -> None:
        self.repository = repository

    async def get_books(self) -> List[models.Book]:
        books = await self.repository.get_books()
        return books

    async def create_book(self, book: BookCreateSchema) -> models.Book:
        new_book = await self.repository.create_book(book)
        return new_book
