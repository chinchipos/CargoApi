import pytest
from httpx import AsyncClient

from src.database.db import sessionmanager
from src.database.models import System
from src.repositories.base import BaseRepository
from tests.conftest import headers

from sqlalchemy import select as sa_select


@pytest.mark.incremental
@pytest.mark.order(3)
class TestSystem:

    """
    Создание записи
    """

    # Ошибка создания нового поставщика услуг: неполные данные
    async def test_create_system_with_incomplete_data(self, aclient: AsyncClient, token: str):
        response = await aclient.post(
            url="/system/create",
            json={
                "full_name": "Газпромнефть",
                "short_name": "ГПН",
                "contract_num": "12-25/99",
                "login": "cargonomica"
            },
            headers=headers(token)
        )

        msg = "Не пройдена проверка на неполные данные"
        assert response.status_code == 422, msg

    # Ошибка создания нового поставщика услуг: некорректный тип данных
    async def test_create_system_with_incorrect_data(self, aclient: AsyncClient, token: str):
        response = await aclient.post(
            url="/system/create",
            json={
                "full_name": "Газпромнефть",
                "short_name": "ГПН",
                "contract_num": "12-25/99",
                "login": "cargonomica",
                "password": "cargonomica",
                "transaction_days": "test"
            },
            headers=headers(token)
        )
        msg = "Не пройдена проверка на некорректный формат данных"
        assert response.status_code == 422, msg

    # Создание нового поставщика услуг
    async def test_create_system(self, aclient: AsyncClient, token: str):
        response = await aclient.post(
            url="/system/create",
            json={
                "full_name": "Газпромнефть1",
                "short_name": "ГПН1",
                "contract_num": "12-25/991",
                "login": "cargonomica1",
                "password": "cargonomica1",
                "transaction_days": 10
            },
            headers=headers(token)
        )
        msg = "Не удалось создать нового поставщика услуг"
        assert response.status_code == 200, msg

    # Ошибка создания нового поставщика услуг: попытка создать аналогичную запись
    async def test_create_duplicate_system(self, aclient: AsyncClient, token: str):
        response = await aclient.post(
            url="/system/create",
            json={
                "full_name": "Газпромнефть1",
                "short_name": "ГПН1",
                "contract_num": "12-25/991",
                "login": "cargonomica1",
                "password": "cargonomica1",
                "transaction_days": 10
            },
            headers=headers(token)
        )
        body = response.json()

        msg = "Не пройдена проверка на дубликат"
        assert response.status_code == 400 and body.get('message', None) and 'идентичную' in body['message'], msg

    # Проверка полноты возвращаемых данных
    async def test_output_data_completeness(self, aclient: AsyncClient, token: str):
        response = await aclient.post(
            url="/system/create",
            json={
                "full_name": "Лукойл",
                "short_name": "Лукойл",
                "contract_num": "22-77/63",
                "login": "cargonomica",
                "password": "cargonomica",
                "transaction_days": 30
            },
            headers=headers(token)
        )
        body = response.json()
        if response.status_code != 200:
            print(body)

        async with sessionmanager.session() as session:
            repository = BaseRepository(session, None)
            stmt = sa_select(System).where(System.full_name == 'Лукойл')
            system = await repository.select_first(stmt)

        correct_response_data = {
            "id": system.id,
            "full_name": system.full_name,
            "short_name": system.short_name,
            "contract_num": system.contract_num,
            "login": system.login,
            "transaction_days": 30,
            "balance": 0,
            "transactions_sync_dt": None,
            "cards_sync_dt": None,
            "balance_sync_dt": None,
            "cards_amount": 0
        }

        msg = "Не пройдена проверка на полноту возвращаемых данных"
        assert response.status_code == 200 and body == correct_response_data, msg

    """
    Редактирование записи
    """

    async def test_edit_system(self, aclient: AsyncClient, token: str):
        async with sessionmanager.session() as session:
            repository = BaseRepository(session, None)
            stmt = sa_select(System).where(System.full_name == 'Газпромнефть1')
            system = await repository.select_first(stmt)

        response = await aclient.post(
            url=f"/system/{system.id}/edit",
            json={
                "full_name": "Газпромнефть",
                "short_name": "ГПН",
                "contract_num": "12-25/99",
                "login": "cargonomica",
                "password": "cargonomica",
                "transaction_days": 50
            },
            headers=headers(token)
        )
        body = response.json()
        if response.status_code != 200:
            print(body)
        correct_response_data = {
            "id": system.id,
            "full_name": "Газпромнефть",
            "short_name": "ГПН",
            "contract_num": "12-25/99",
            "login": "cargonomica",
            "transaction_days": 50,
            "balance": 0,
            "transactions_sync_dt": None,
            "cards_sync_dt": None,
            "balance_sync_dt": None,
            "cards_amount": 0
        }

        msg = "Не пройдена проверка на редактирование записи"
        assert response.status_code == 200 and body == correct_response_data, msg

    """
    Получение всех записей
    """

    async def test_get_all_systems(self, aclient: AsyncClient, token: str):
        response = await aclient.get(
            url=f"/system/all",
            headers=headers(token)
        )
        body = response.json()
        if response.status_code != 200:
            print(body)

        msg = "Не пройдена проверка на получение всех записей"
        assert response.status_code == 200 and len(body) == 2, msg

    """
    Удаление записи
    """

    async def test_delete_system(self, aclient: AsyncClient, token: str):
        async with sessionmanager.session() as session:
            repository = BaseRepository(session, None)
            stmt = sa_select(System).where(System.full_name == 'Лукойл')
            system = await repository.select_first(stmt)

        response = await aclient.get(
            url=f"/system/{system.id}/delete",
            headers=headers(token)
        )

        async with sessionmanager.session() as session:
            repository = BaseRepository(session, None)
            stmt = sa_select(System).where(System.full_name == 'Лукойл')
            system = await repository.select_first(stmt)

        msg = "Не пройдена проверка на удаление записи"
        assert response.status_code == 200 and system is None, msg
