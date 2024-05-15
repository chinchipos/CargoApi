from fastapi import Depends

from src.auth.auth import current_active_user
from src.database.db import get_session, SessionLocal
from src.database.models import User
from src.repositories.card import CardRepository
from src.repositories.card_type import CardTypeRepository
from src.repositories.company import CompanyRepository
from src.repositories.db import DBRepository
from src.repositories.system import SystemRepository
from src.repositories.tariff import TariffRepository
from src.repositories.user import UserRepository
from src.services.card import CardService
from src.services.card_type import CardTypeService
from src.services.company import CompanyService
from src.services.db import DBService
from src.services.system import SystemService
from src.services.tariff import TariffService
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


def get_service_tariff(
    session: SessionLocal = Depends(get_session),
    user: User = Depends(current_active_user)
) -> TariffService:
    repository = TariffRepository(session, user.id)
    service = TariffService(repository)
    return service


def get_service_card_type(
    session: SessionLocal = Depends(get_session),
    user: User = Depends(current_active_user)
) -> CardTypeService:
    repository = CardTypeRepository(session, user.id)
    service = CardTypeService(repository)
    return service


def get_service_card(
    session: SessionLocal = Depends(get_session),
    user: User = Depends(current_active_user)
) -> CardService:
    repository = CardRepository(session, user.id)
    service = CardService(repository)
    return service
