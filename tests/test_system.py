import pytest
from httpx import AsyncClient

from tests.conftest import headers


@pytest.mark.incremental
@pytest.mark.order(3)
class TestSystem:

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

        msg = "Не выполнена проверка на неполные данные"
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
        msg = "Не выполнена проверка на некорректный формат данных"
        assert response.status_code == 422, msg

    # Создание нового поставщика услуг
    async def test_create_system_operation(self, aclient: AsyncClient, token: str):
        response = await aclient.post(
            url="/system/create",
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
        msg = "Не удалось создать нового поставщика услуг"
        assert response.status_code == 200, msg

    # Ошибка создания нового поставщика услуг: попытка создать аналогичную запись
    async def test_create_system_duplicate(self, aclient: AsyncClient, token: str):
        response = await aclient.post(
            url="/system/create",
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

        msg = "Не выполнена проверка на дубликат"
        assert response.status_code == 400 and body.get('message', None) and 'идентичную' in body['message'], msg
