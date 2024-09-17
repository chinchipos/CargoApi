from celery import Celery

from src.config import PROD_URI, REDIS_HOST, REDIS_PORT, PRODUCTION, REDIS_DB, REDIS_USER, REDIS_PASSWORD

if REDIS_USER or REDIS_PASSWORD:
    redis_server = f'redis://{REDIS_USER}:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
else:
    redis_server = f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'

if PRODUCTION:
    sa_result_backend = (
        PROD_URI.replace("postgresql+psycopg", "db+postgresql") + "?sslmode=verify-full&target_session_attrs=read-write"
    )

else:
    sa_result_backend = PROD_URI.replace("postgresql+psycopg", "db+postgresql") + "?target_session_attrs=read-write"

celery = Celery('cargonomica', backend=sa_result_backend, broker=redis_server)
celery.conf.broker_connection_retry_on_startup = True
celery.conf.broker_connection_max_retries = 10
celery.conf.timezone = 'Europe/Moscow'
celery.autodiscover_tasks(
    packages=[
        "src.celery_app.sync",
        "src.celery_app.balance",
        "src.celery_app.overdraft",
        "src.celery_app.khnp",
        "src.celery_app.gpn",
        "src.celery_app.ops",
        "src.celery_app.limits",
        "src.celery_app.test",
    ]
)
