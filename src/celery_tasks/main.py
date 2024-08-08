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
        "src.celery_tasks.sync",
        "src.celery_tasks.balance",
        "src.celery_tasks.overdraft",
        "src.celery_tasks.khnp",
        "src.celery_tasks.gpn",
        "src.celery_tasks.limits"
    ]
)
