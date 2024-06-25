import pytest
from httpx import AsyncClient
from sqlalchemy import select as sa_select, text

from src.database.db import sessionmanager
from src.database.models import Company, Role
from src.repositories.base import BaseRepository
from src.utils import enums
from tests.conftest import headers


@pytest.mark.incremental
@pytest.mark.order(6)
class TestSystem:

    """
    Создание записи
    """

    # Создание нового пользователя организации
    async def test_create_company_admin(self, aclient: AsyncClient, token: str):
        async with sessionmanager.session() as session:
            repository = BaseRepository(session, None)

            # Получаем организацию
            stmt = sa_select(Company).where(Company.name == 'ООО "Ромашка"')
            company = await repository.select_first(stmt)
            print(company.id)

            # Получаем роль
            stmt = sa_select(Role).where(Role.name == enums.Role.COMPANY_ADMIN.name)
            role = await repository.select_first(stmt)
            print(role.id)

            response = await aclient.post(
                url="/user/create",
                json={
                    "user": {
                      "email": "efimov@cargonomica.com",
                      "password": "One2345!",
                      "is_active": True,
                      "username": "efimov",
                      "first_name": "Михаил",
                      "last_name": "Ефимов",
                      "phone": "89532244667",
                      "role_id": role.id,
                      "company_id": company.id
                    }
                },
                headers=headers(token)
            )

            msg = "Не удалось создать нового администратора компании"
            assert response.status_code == 200, msg

    # Создание нового менеджера организаций
    async def test_create_cargo_manager(self, aclient: AsyncClient, token: str):
        async with sessionmanager.session() as session:
            repository = BaseRepository(session, None)

            # Получаем организации
            stmt = sa_select(Company).where(Company.name.in_(['ООО "Ромашка"', 'ООО "Дильшот Логистикс"']))
            companies = await repository.select_all(stmt)

            # Получаем роль
            stmt = sa_select(Role).where(Role.name == enums.Role.CARGO_MANAGER.name)
            role = await repository.select_first(stmt)

            response = await aclient.post(
                url="/user/create",
                json={
                    "user": {
                        "email": "grin@cargonomica.com",
                        "password": "One2345!",
                        "is_active": True,
                        "username": "grin",
                        "first_name": "Грин",
                        "last_name": "Анастасия",
                        "phone": "89532244668",
                        "role_id": role.id
                    },
                    "managed_companies": [companies[0].id, companies[1].id]
                },
                headers=headers(token)
            )

            msg = "Не удалось создать нового менеджера организаций"
            assert response.status_code == 200, msg
