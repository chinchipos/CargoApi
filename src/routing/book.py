from typing import List

from fastapi import APIRouter, Depends

from src.depends import get_service_book
from src.schemas.book import BookViewSchema, BookCreateSchema
from src.services.book import BookService
from src.utils.schemas import Message

router = APIRouter(prefix="/book", tags=["book"])


@router.get(
    "",
    responses = {400: {'model': Message, "description": "Bad request"}},
    response_model = List[BookViewSchema],
    description = "Получение листинга всех книг",
)
async def get_all_books(
    book_service: BookService = Depends(get_service_book)
):
    books = await book_service.get_books()
    return books


@router.post(
    "",
    responses = {400: {'model': Message, "description": "Bad request"}},
    response_model = BookViewSchema,
    description = "Создание книги",
)
async def create_book(
    book: BookCreateSchema,
    book_service: BookService = Depends(get_service_book)
):
    new_book = await book_service.create_book(book)
    return new_book
