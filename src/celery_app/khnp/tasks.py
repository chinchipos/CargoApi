import asyncio
import sys
from typing import Dict, List

from src.celery_app.irrelevant_balances import IrrelevantBalances
from src.celery_app.khnp.api import KHNPParser
from src.celery_app.khnp.controller import KHNPController
from src.celery_app.main import celery
from src.config import PROD_URI
from src.database.db import DatabaseSessionManager
from src.utils.loggers import get_logger

_logger = get_logger(name="KHNP_TASKS", filename="celery.log")


async def khnp_sync_fn() -> IrrelevantBalances:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        khnp = KHNPController(session)
        irrelevant_balances = await khnp.sync()

    # Закрываем соединение с БД
    await sessionmanager.close()
    _logger.info('Синхронизация с ХНП успешно завершена')
    return irrelevant_balances


@celery.task(name="SYNC_KHNP")
def khnp_sync() -> IrrelevantBalances:
    _logger.info("Запускаю синхронизацию с ХНП")
    try:
        return asyncio.run(khnp_sync_fn())
    except Exception as e:
        _logger.exception(str(e))
        _logger.info("Ошибка синхронизации с ХНП")


async def khnp_set_card_states_fn(balance_ids_to_change_card_states: Dict[str, List[str]]) -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        khnp_controller = KHNPController(session)
        await khnp_controller.set_card_states(balance_ids_to_change_card_states)

    # Закрываем соединение с БД
    await sessionmanager.close()


@celery.task(name="KHNP_SET_CARD_STATES")
def khnp_set_card_states(balance_ids_to_change_card_states: Dict[str, List[str]]) -> str:
    if balance_ids_to_change_card_states["to_block"] or balance_ids_to_change_card_states["to_activate"]:
        _logger.info('Запускаю задачу блокировки / разблокировки карт ХНП')

        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        # asyncio.run(khnp_set_card_states_fn(balance_ids_to_change_card_states))

    else:
        _logger.info('Блокировка / разблокировка карт не требуется: '
                     'не было транзакций с момента последней синхронизации')

    return "COMPLETE"


@celery.task(name="KHNP_SET_CARD_STATE")
def khnp_set_card_state(card_number: str, activate: bool) -> None:
    action = "разблокировки" if activate else "блокировки"
    _logger.info(f'Запускаю задачу {action} карты ХНП')
    khnp_api = KHNPParser()
    khnp_api.login()
    khnp_api.set_card_state(card_number, activate)
