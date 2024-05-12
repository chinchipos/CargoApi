from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from src import config


URI = "postgresql+psycopg://{}:{}@{}:{}/{}".format(
    config.DB_USER,
    config.DB_PASSWORD,
    config.DB_FQDN_HOST,
    config.DB_PORT,
    config.DB_NAME
)
engine = create_async_engine(
    URI,
    connect_args = {'sslmode': "verify-full", 'target_session_attrs': 'read-write'},
    pool_size = 10,
    max_overflow = 5,
    echo = True
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


# Dependency
async def get_session():
    try:
        async with SessionLocal() as session:
            yield session
    finally:
        await engine.dispose()
