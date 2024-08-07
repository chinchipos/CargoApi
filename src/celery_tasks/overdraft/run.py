import asyncio
import sys

from src.celery_tasks.exceptions import celery_logger
from src.celery_tasks.overdraft.tasks import overdraft_chain


def run_calc_overdrafts():
    celery_logger.info('Запускаю задачу рачсета овердрафтов')

    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    overdraft_chain()


def run_sending_overdraft_reports():
    celery_logger.info('Запускаю задачу рассылки отчетов по овердрафтам')

    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    overdraft_chain()
