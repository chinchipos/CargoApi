import pytest
from httpx import AsyncClient
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.database.db import sessionmanager
from src.database.model.models import Tariff
from tests.conftest import headers


@pytest.mark.incremental
@pytest.mark.order(4)
class TestSystem:

    """
    Создание записи
    """

    # Создание нового тарифа
    async def test_create_tariff(self, aclient: AsyncClient, token: str):
        response = await aclient.post(
            url="/tariff/create",
            json={
                "name": "Полпроцента",
                "fee_percent": 0.5
            },
            headers=headers(token)
        )
        msg = "Не удалось создать тариф"
        assert response.status_code == 200, msg

    # Создаем еще пару тарифов
    async def test_create_more_tariffs(self):
        dataset = [
            {
                "name": "Полтора процента",
                "fee_percent": 1.5
            },
            {
                "name": "Два процента",
                "fee_percent": 2
            },
        ]
        async with sessionmanager.session() as session:
            stmt = pg_insert(Tariff)
            async with session.begin():
                await session.execute(stmt, dataset)
                await session.commit()

        msg = "Не удалось создать дополнительные тарифы"
        assert 1 == 1, msg
