import pytest
from httpx import AsyncClient
from tests.conftest import Config
from sqlalchemy import select as sa_select

from src.config import SERVICE_TOKEN
from src.database import models
from src.database.db import sessionmanager
from src.repositories.base import BaseRepository


@pytest.mark.incremental
@pytest.mark.order(2)
class TestUser:

    # Инициализация БД
    async def test_user_auth(self, aclient: AsyncClient, config_obj: Config):
        response = await aclient.post(
            url="/auth/jwt/login",
            data={
                "username": 'cargo@cargonomica.com',
                "password": "One2345!"
            },
        )
        body = response.json()
        config_obj.TOKEN = body.get('access_token', None)

        msg = "Не удалось выполнить авторизацию"
        assert response.status_code == 200 and body.get('access_token', None), msg
