from fastapi import Depends

from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.auth import get_current_active_user
from src.database.db import get_session
from src.database.models.user import UserOrm
from src.repositories.azs import AzsRepository
from src.repositories.car import CarRepository
from src.repositories.card import CardRepository
from src.repositories.card_type import CardTypeRepository
from src.repositories.company import CompanyRepository
from src.repositories.db.db import DBRepository
from src.repositories.filter import FilterRepository
from src.repositories.goods import GoodsRepository
from src.repositories.role import RoleRepository
from src.repositories.system import SystemRepository
from src.repositories.tariff import TariffRepository
from src.repositories.transaction import TransactionRepository
from src.repositories.user import UserRepository
from src.services.azs import AzsService
from src.services.car import CarService
from src.services.card import CardService
from src.services.card_type import CardTypeService
from src.services.company import CompanyService
from src.services.db import DBService
from src.services.filter import FilterService
from src.services.goods import GoodsService
from src.services.role import RoleService
from src.services.system import SystemService
from src.services.tariff import TariffService
from src.services.transaction import TransactionService
from src.services.user import UserService

"""
Файл внедрения зависимостей
"""


def get_service_db(
    session: AsyncSession = Depends(get_session)
) -> DBService:
    repository = DBRepository(session, None)
    service = DBService(repository)
    return service


def get_service_user(
    session: AsyncSession = Depends(get_session),
    user: UserOrm = Depends(get_current_active_user)
) -> UserService:
    repository = UserRepository(session, user)
    service = UserService(repository)
    return service


def get_service_system(
    session: AsyncSession = Depends(get_session),
    user: UserOrm = Depends(get_current_active_user)
) -> SystemService:
    repository = SystemRepository(session, user)
    service = SystemService(repository)
    return service


def get_service_company(
    session: AsyncSession = Depends(get_session),
    user: UserOrm = Depends(get_current_active_user)
) -> CompanyService:
    repository = CompanyRepository(session, user)
    service = CompanyService(repository)
    return service


def get_service_tariff(
    session: AsyncSession = Depends(get_session),
    user: UserOrm = Depends(get_current_active_user)
) -> TariffService:
    repository = TariffRepository(session, user)
    service = TariffService(repository)
    return service


def get_service_card_type(
    session: AsyncSession = Depends(get_session),
    user: UserOrm = Depends(get_current_active_user)
) -> CardTypeService:
    repository = CardTypeRepository(session, user)
    service = CardTypeService(repository)
    return service


def get_service_card(
    session: AsyncSession = Depends(get_session),
    user: UserOrm = Depends(get_current_active_user)
) -> CardService:
    repository = CardRepository(session, user)
    service = CardService(repository)
    return service


def get_service_transaction(
    session: AsyncSession = Depends(get_session),
    user: UserOrm = Depends(get_current_active_user)
) -> TransactionService:
    repository = TransactionRepository(session, user)
    service = TransactionService(repository)
    return service


def get_service_car(
    session: AsyncSession = Depends(get_session),
    user: UserOrm = Depends(get_current_active_user)
) -> CarService:
    repository = CarRepository(session, user)
    service = CarService(repository)
    return service


def get_service_role(
    session: AsyncSession = Depends(get_session),
    user: UserOrm = Depends(get_current_active_user)
) -> RoleService:
    repository = RoleRepository(session, user)
    service = RoleService(repository)
    return service


def get_service_goods(
    session: AsyncSession = Depends(get_session),
    user: UserOrm = Depends(get_current_active_user)
) -> GoodsService:
    repository = GoodsRepository(session, user)
    service = GoodsService(repository)
    return service


def get_service_azs(
    session: AsyncSession = Depends(get_session),
    user: UserOrm = Depends(get_current_active_user)
) -> AzsService:
    repository = AzsRepository(session, user)
    service = AzsService(repository)
    return service


def get_service_filter(
    session: AsyncSession = Depends(get_session),
    user: UserOrm = Depends(get_current_active_user)
) -> FilterService:
    repository = FilterRepository(session, user)
    service = FilterService(repository)
    return service
