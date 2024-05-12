from fastapi import Depends

from src.auth.auth import current_active_user
from src.database.db import get_session, SessionLocal
from src.database.models import User
from src.repositories.author import AuthorRepository
from src.repositories.book import BookRepository
from src.repositories.db import DBRepository
from src.repositories.user import UserRepository
from src.services.author import AuthorService
from src.services.book import BookService
from src.services.db import DBService
from src.services.user import UserService

"""
Файл внедрения зависимостей
"""


def get_service_author(
    session: SessionLocal = Depends(get_session),
    user: User = Depends(current_active_user)
) -> AuthorService:
    # repository - работа с БД
    author_repository = AuthorRepository(session)
    # service - слой UseCase
    author_service = AuthorService(author_repository, user)

    return author_service


def get_service_book(
    session: SessionLocal = Depends(get_session)
) -> BookService:
    # repository - работа с БД
    book_repository = BookRepository(session)
    # service - слой UseCase
    book_service = BookService(book_repository)
    return book_service


def get_service_db(
    session: SessionLocal = Depends(get_session)
) -> DBService:
    repository = DBRepository(session, None)
    service = DBService(repository)
    return service


def get_service_user(
    session: SessionLocal = Depends(get_session),
    user: User = Depends(current_active_user)
) -> UserService:
    repository = UserRepository(session, user.id)
    service = UserService(repository)
    return service
