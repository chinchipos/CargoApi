import asyncio
import sys
from typing import Dict, List

from src.celery_tasks.exceptions import celery_logger
from src.celery_tasks.gpn.api import GPNApi
from src.celery_tasks.main import celery
from src.config import PROD_URI
from src.celery_tasks.gpn.controller import GPNController
from src.celery_tasks.irrelevant_balances import IrrelevantBalances
from src.database.db import DatabaseSessionManager


async def gpn_sync_fn() -> IrrelevantBalances:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        gpn = GPNController(session, celery_logger)
        irrelevant_balances = await gpn.sync()

    # Закрываем соединение с БД
    await sessionmanager.close()
    celery_logger.info('Синхронизация с ГПН успешно завершена')
    return irrelevant_balances


@celery.task(name="SYNC_GPN")
def gpn_sync() -> IrrelevantBalances:
    celery_logger.info("Запускаю синхронизацию с ГПН")
    return asyncio.run(gpn_sync_fn())


async def gpn_set_card_states_fn(balance_ids_to_change_card_states: Dict[str, List[str]]) -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        gpn_controller = GPNController(session, celery_logger)
        await gpn_controller.set_card_states(balance_ids_to_change_card_states)

    # Закрываем соединение с БД
    await sessionmanager.close()


@celery.task(name="GPN_SET_CARD_STATES")
def gpn_set_card_states(balance_ids_to_change_card_states: Dict[str, List[str]]) -> str:
    if balance_ids_to_change_card_states["to_block"] or balance_ids_to_change_card_states["to_activate"]:
        celery_logger.info('Запускаю задачу блокировки / разблокировки карт ГПН')

        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        asyncio.run(gpn_set_card_states_fn(balance_ids_to_change_card_states))

    else:
        celery_logger.info('Блокировка / разблокировка карт не требуется: '
                           'не было транзакций с момента последней синхронизации')

    return "COMPLETE"


async def gpn_cards_bind_company_fn(card_ids: List[str], personal_account: str, limit_sum: int | float) -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        gpn = GPNController(session, celery_logger)
        await gpn.gpn_bind_company_to_cards(card_ids, personal_account, limit_sum)

    # Закрываем соединение с БД
    await sessionmanager.close()


@celery.task(name="GPN_CARDS_BIND_COMPANY")
def gpn_cards_bind_company(card_ids: List[str], personal_account: str, limit_sum: int | float) -> None:
    asyncio.run(gpn_cards_bind_company_fn(card_ids, personal_account, limit_sum))


async def gpn_cards_unbind_company_fn(card_ids: List[str]) -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        gpn = GPNController(session, celery_logger)
        await gpn.gpn_unbind_company_from_cards(card_ids)

    # Закрываем соединение с БД
    await sessionmanager.close()


@celery.task(name="GPN_CARD_UNBIND_COMPANY")
def gpn_cards_unbind_company(card_ids: List[str]) -> None:
    asyncio.run(gpn_cards_unbind_company_fn(card_ids))


async def sync_gpn_cards_fn() -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        gpn = GPNController(session, celery_logger)
        await gpn.sync_cards()

    # Закрываем соединение с БД
    await sessionmanager.close()


@celery.task(name="SYNC_GPN_CARDS")
def sync_gpn_cards() -> None:
    asyncio.run(sync_gpn_cards_fn())


async def gpn_test_fn() -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        gpn_api = GPNApi(celery_logger)
        gpn_api.gpn_test()

    # Закрываем соединение с БД
    await sessionmanager.close()


@celery.task(name="GPN_TEST")
def gpn_test() -> None:
    asyncio.run(gpn_test_fn())
