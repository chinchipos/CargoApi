import contextlib
from typing import AsyncIterator, AsyncGenerator

from psycopg import AsyncConnection
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncEngine

from src.config import PRODUCTION, SQLALCHEMY_ECHO
from src.database.models import Base


class DatabaseSessionManager:
    def __init__(self):
        self._engine: AsyncEngine | None = None
        self._sessionmaker: async_sessionmaker | None = None

    def init(self, connection_string: str, tests: bool = False):
        if tests:
            echo = False
        else:
            echo = SQLALCHEMY_ECHO

        self._engine = create_async_engine(
            connection_string,
            connect_args={'sslmode': "verify-full", 'target_session_attrs': 'read-write'},
            pool_size=10,
            max_overflow=5,
            echo=echo
        )
        self._sessionmaker = async_sessionmaker(bind=self._engine, expire_on_commit=False)

    def get_engine(self):
        return self._engine

    async def close(self):
        if self._engine is None:
            raise Exception("DatabaseSessionManager is not initialized")
        await self._engine.dispose()
        self._engine = None
        self._sessionmaker = None

    @contextlib.asynccontextmanager
    async def connect(self) -> AsyncIterator[AsyncConnection]:
        if self._engine is None:
            raise Exception("DatabaseSessionManager is not initialized")

        async with self._engine.begin() as connection:
            try:
                yield connection
            except Exception:
                await connection.rollback()
                raise

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        if self._sessionmaker is None:
            raise Exception("DatabaseSessionManager is not initialized")

        session = self._sessionmaker()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    # Used for testing
    async def create_all(self):
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_all(self):
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)


sessionmanager = DatabaseSessionManager()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with sessionmanager.session() as session:
        yield session
