import asyncio
import os
from contextlib import ExitStack
from typing import AsyncGenerator, Optional

import pytest
from dotenv import load_dotenv
from httpx import AsyncClient, ASGITransport

from src.database.db import sessionmanager
from src.main import init_app

from fastapi.testclient import TestClient

load_dotenv()
DB_USER_TEST = os.environ.get('DB_USER_TEST')
DB_PASSWORD_TEST = os.environ.get('DB_PASSWORD_TEST')
DB_FQDN_HOST_TEST = os.environ.get('DB_FQDN_HOST_TEST')
DB_PORT_TEST = os.environ.get('DB_PORT_TEST')
DB_NAME_TEST = os.environ.get('DB_NAME_TEST')

TEST_URI = "postgresql+psycopg://{}:{}@{}:{}/{}".format(
    DB_USER_TEST,
    DB_PASSWORD_TEST,
    DB_FQDN_HOST_TEST,
    DB_PORT_TEST,
    DB_NAME_TEST
)


class Config:
    TOKEN: Optional[str] = None


config = Config()


@pytest.fixture(autouse=True, scope='session')
async def app():
    with ExitStack():
        app = init_app(TEST_URI, tests = True)
        await sessionmanager.drop_all()
        await sessionmanager.create_all()
        yield app


@pytest.fixture(scope="session")
async def aclient(app) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as aclient:
        yield aclient


@pytest.fixture(scope="session")
def event_loop_policy(request):
    return asyncio.WindowsSelectorEventLoopPolicy()


def pytest_runtest_makereport(item, call):
    if "incremental" in item.keywords:
        if call.excinfo is not None:
            parent = item.parent
            parent._previousfailed = item


def pytest_runtest_setup(item):
    previousfailed = getattr(item.parent, "_previousfailed", None)
    if previousfailed is not None:
        pytest.xfail("previous test failed (%s)" % previousfailed.name)


@pytest.fixture(scope="session")
def client(app):
    return TestClient(app=app)


@pytest.fixture(scope="function")
async def config_obj() -> Config:
    return config


@pytest.fixture(scope="function")
async def token() -> Optional[str]:
    return config.TOKEN


def headers(token: str):
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }
