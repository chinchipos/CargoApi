from typing import AsyncGenerator

from fastapi import Depends
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src import config
from src.database.db import get_session
from src.database.models import User

'''
DATABASE_URL = "postgresql+psycopg://{}:{}@{}:{}/{}?sslmode=verify-full&target_session_attrs=read-write".format(
    config.DB_USER,
    config.DB_PASSWORD,
    config.DB_FQDN_HOST,
    config.DB_PORT,
    config.DB_NAME
)


engine = create_async_engine(DATABASE_URL)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
'''

async def get_user_db(session: AsyncSession = Depends(get_session)):
    yield SQLAlchemyUserDatabase(session, User)
