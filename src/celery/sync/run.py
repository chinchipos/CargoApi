import asyncio
import sys

from src.celery.exceptions import celery_logger
from src.celery.sync.tasks import sync_chain


def run_sync_systems():
    celery_logger.info('Запускаю задачу синхронизации с системами поставщиков')

    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    sync_chain()
