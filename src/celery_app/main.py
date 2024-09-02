from celery import Celery

from src.config import PROD_URI

redis_server = 'redis://localhost:6379'
sa_result_backend = (PROD_URI.replace("postgresql+psycopg", "db+postgresql") +
                     "?sslmode=verify-full&target_session_attrs=read-write")

celery = Celery('cargonomica', backend=sa_result_backend, broker=f'{redis_server}/0')
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
