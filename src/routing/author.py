from typing import List

from fastapi import APIRouter, Depends

from src.depends import get_service_author
from src.schemas.author import AuthorViewSchema, AuthorCreateSchema
from src.services.author import AuthorService
from src.utils.schemas import MessageSchema

router = APIRouter(prefix="/author", tags=["author"])


@router.get(
    "",
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[AuthorViewSchema],
    description = "Получение листинга всех авторов",
)
async def get_all_authors(
    author_service: AuthorService = Depends(get_service_author)
):
    authors = await author_service.get_authors()
    return authors


@router.post(
    "",
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = AuthorViewSchema,
    description = "Создание автора",
)
async def create_book(
    author: AuthorCreateSchema,
    author_service: AuthorService = Depends(get_service_author)
):
    new_author = await author_service.create_author(author)
    return new_author
