import asyncio
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.sql.ddl import CreateSchema

from src.config import PROD_URI, SCHEMA, SSL_REQUIRED
from src.database.db import DatabaseSessionManager
from src.database.models.base import Base

from celery.backends.database.session import ResultModelBase

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

if SSL_REQUIRED:
    config.set_main_option("sqlalchemy.url", PROD_URI + "?sslmode=verify-full&target_session_attrs=read-write")
else:
    config.set_main_option("sqlalchemy.url", PROD_URI + "?target_session_attrs=read-write")

target_metadata = [Base.metadata, ResultModelBase.metadata]


# Создаем схему, если она не существует
async def create_schema_if_not_exists() -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)
    async with sessionmanager.get_engine().begin() as connection:
        await connection.execute(CreateSchema(SCHEMA, if_not_exists=True))


async def add_ossp_extansion_if_not_exists() -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)
    async with sessionmanager.get_engine().begin() as connection:
        await connection.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        await connection.commit()


async def create_sequence_for_celery_if_not_exists() -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)
    async with sessionmanager.get_engine().begin() as connection:
        await connection.execute(text('CREATE SEQUENCE IF NOT EXISTS task_id_sequence START WITH 1'))
        await connection.commit()


if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

asyncio.run(create_schema_if_not_exists())
asyncio.run(add_ossp_extansion_if_not_exists())
asyncio.run(create_sequence_for_celery_if_not_exists())


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        dialect_name="postgrsql",
        dialect_opts={"paramstyle": "named"},
        target_metadata=target_metadata,
        version_table_schema=Base.metadata.schema,
        literal_binds=True,
        include_schemas=True,
        compare_server_default=True
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        dialect_name="postgrsql",
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        compare_server_default=True
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
