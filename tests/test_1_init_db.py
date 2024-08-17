import pytest
from httpx import AsyncClient
from sqlalchemy import select as sa_select

from src.config import SERVICE_TOKEN
from src.database.models.card_type import CardTypeOrm
from src.database.models.role import RoleOrm
from src.database.models.user import UserOrm
from src.database.db import sessionmanager
from src.repositories.base import BaseRepository


@pytest.mark.incremental
@pytest.mark.order(1)
class TestInitDB:

    # Инициализация БД
    async def test_init_db_weak_password(self, aclient: AsyncClient):
        response = await aclient.post("/db/init", json={
            "service_token": SERVICE_TOKEN,
            "superuser_password": "12341234"
        })
        body = response.json()
        msg = "Не выполнена проверка сложности пароля"
        assert response.status_code == 400 and body.get('message', None) and 'сложности' in body['message'], msg

    async def test_init_db(self, aclient: AsyncClient):
        response = await aclient.post("/db/init", json={
            "service_token": SERVICE_TOKEN,
            "superuser_password": "One2345!"
        })
        msg = "Не удалось выполнить операцию: Инициализация БД"
        assert response.status_code == 200, msg

    # Проверяем правильность создания ролей
    async def test_init_roles_created_successfully(self):
        async with sessionmanager.session() as session:
            repository = BaseRepository(session, None)

            stmt = sa_select(RoleOrm)
            roles = await repository.select_all(stmt)
            role_names = [role.name for role in roles]
            roles_list = ['CARGO_SUPER_ADMIN', 'CARGO_MANAGER', 'COMPANY_ADMIN', 'COMPANY_LOGIST', 'COMPANY_DRIVER']

            msg = "Созданные роли не соответствуют инициализационным значениям, при этом запрос к API не вернул ошибку"
            assert role_names == roles_list, msg

    # Проверяем правильность создания типов карт
    async def test_init_card_types_created_successfully(self):
        async with sessionmanager.session() as session:
            repository = BaseRepository(session, None)

            stmt = sa_select(CardTypeOrm)
            card_types = await repository.select_all(stmt)
            card_type_names = [card_type.name for card_type in card_types]

            msg = "Созданные типы карт не соответствуют инициализационным значениям, при этом запрос к API не \
                вернул ошибку"
            assert card_type_names == ['Пластиковая карта', 'Виртуальная карта'], msg

    # Проверяем правильность создания суперадмина
    async def test_cargo_superadmin_created_successfully(self):
        async with sessionmanager.session() as session:
            repository = BaseRepository(session, None)

            stmt = sa_select(UserOrm).where(UserOrm.email == 'cargo@cargonomica.com')
            cargo_superadmin = await repository.select_first(stmt)

            msg = "Суперпользователь не создан, при этом запрос к API не вернул ошибку"
            assert cargo_superadmin and cargo_superadmin.username == 'cargo', msg
