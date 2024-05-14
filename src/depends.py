from fastapi import Depends

from src.auth.auth import current_active_user
from src.database.db import get_session, SessionLocal
from src.database.models import User
from src.repositories.company import CompanyRepository
from src.repositories.db import DBRepository
from src.repositories.system import SystemRepository
from src.repositories.user import UserRepository
from src.services.company import CompanyService
from src.services.db import DBService
from src.services.system import SystemService
from src.services.user import UserService

"""
Файл внедрения зависимостей
"""


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


def get_service_system(
    session: SessionLocal = Depends(get_session),
    user: User = Depends(current_active_user)
) -> SystemService:
    repository = SystemRepository(session, user.id)
    service = SystemService(repository)
    return service


def get_service_company(
    session: SessionLocal = Depends(get_session),
    user: User = Depends(current_active_user)
) -> CompanyService:
    repository = CompanyRepository(session, user.id)
    service = CompanyService(repository)
    return service
