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
        "src.celery.sync",
        "src.celery.balance",
        "src.celery.overdraft",
        "src.celery.khnp",
        "src.celery.gpn"
    ]
)


"""
@celery.task(name="ZERO_TASK")
def zero_task() -> Dict[str, Any]:
    return {"p1": 123, "p2": 456}


@celery.task(name="GROUPED_TASK1")
def grouped_task1(data: Dict[str, Any]) -> None:
    print(f"TASK1: {data}")


@celery.task(name="GROUPED_TASK2")
def grouped_task2(data: Dict[str, Any]) -> None:
    print(f"TASK2: {data}")


@shared_task
def dmap(result):
    grouped_tasks = group(
        grouped_task1.s(result),
        grouped_task2.s(result)
    )
    return grouped_tasks()


main_chain = chain(
    zero_task.si(),
    dmap.s()
)
"""
