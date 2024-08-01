import asyncio
import sys
from logging.config import fileConfig
import importlib

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from src.config import PROD_URI
from src.database.model import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", PROD_URI + "?sslmode=verify-full&target_session_attrs=read-write")


models_path = "src.database.model"
want_model_files = (
    f"{models_path}.models",
    f"{models_path}.card",
    f"{models_path}.card_type",
)

for want_model_file in want_model_files:
    try:
        loaded_module = importlib.import_module(want_model_file )
    except ModuleNotFoundError:
        print(f'Could not import module {want_model_file}')

target_metadata = Base.metadata


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
