import asyncio
import sys
from typing import Dict, List

from src.celery_tasks.exceptions import celery_logger
from src.celery_tasks.main import celery
from src.config import PROD_URI
from src.celery_tasks.irrelevant_balances import IrrelevantBalances
from src.celery_tasks.khnp.controller import KHNPController
from src.database.db import DatabaseSessionManager


async def khnp_sync_fn() -> IrrelevantBalances:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        khnp = KHNPController(session, celery_logger)
        irrelevant_balances = await khnp.sync()

    # Закрываем соединение с БД
    await sessionmanager.close()
    celery_logger.info('Синхронизация с ХНП успешно завершена')
    return irrelevant_balances


@celery.task(name="SYNC_KHNP")
def khnp_sync() -> IrrelevantBalances:
    celery_logger.info("Запускаю синхронизацию с ХНП")
    return asyncio.run(khnp_sync_fn())


async def khnp_set_card_states_fn(balance_ids_to_change_card_states: Dict[str, List[str]]) -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        khnp_controller = KHNPController(session=session, logger=celery_logger)
        await khnp_controller.set_card_states(balance_ids_to_change_card_states)

    # Закрываем соединение с БД
    await sessionmanager.close()


@celery.task(name="KHNP_SET_CARD_STATES")
def khnp_set_card_states(balance_ids_to_change_card_states: Dict[str, List[str]]) -> str:
    if balance_ids_to_change_card_states["to_block"] or balance_ids_to_change_card_states["to_activate"]:
        celery_logger.info('Запускаю задачу блокировки / разблокировки карт ХНП')

        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        asyncio.run(khnp_set_card_states_fn(balance_ids_to_change_card_states))

    else:
        celery_logger.info('Блокировка / разблокировка карт не требуется: '
                           'не было транзакций с момента последней синхронизации')

    return "COMPLETE"
