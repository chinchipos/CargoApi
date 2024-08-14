import asyncio
import sys
from typing import Dict, List

from src.celery_app.gpn.api import GPNApi
from src.celery_app.gpn.controller import GPNController
from src.celery_app.irrelevant_balances import IrrelevantBalances
from src.celery_app.main import celery
from src.config import PROD_URI
from src.database.db import DatabaseSessionManager
from src.utils.loggers import get_logger

_logger = get_logger(name="GPN_TASKS", filename="celery.log")


async def gpn_sync_fn() -> IrrelevantBalances:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        gpn = GPNController(session)
        irrelevant_balances = await gpn.sync()

    # Закрываем соединение с БД
    await sessionmanager.close()
    _logger.info('Синхронизация с ГПН успешно завершена')
    return irrelevant_balances


@celery.task(name="SYNC_GPN")
def gpn_sync() -> IrrelevantBalances:
    _logger.info("Запускаю синхронизацию с ГПН")
    try:
        return asyncio.run(gpn_sync_fn())
    except Exception as e:
        _logger.exception(str(e))
        _logger.info("Ошибка синхронизации с ГПН")


async def gpn_set_card_states_fn(balance_ids_to_change_card_states: Dict[str, List[str]]) -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        gpn_controller = GPNController(session)
        await gpn_controller.set_card_states(balance_ids_to_change_card_states)

    # Закрываем соединение с БД
    await sessionmanager.close()


@celery.task(name="GPN_SET_CARD_STATES")
def gpn_set_card_states(balance_ids_to_change_card_states: Dict[str, List[str]]) -> str:
    if balance_ids_to_change_card_states["to_block"] or balance_ids_to_change_card_states["to_activate"]:
        _logger.info('Запускаю задачу блокировки / разблокировки карт ГПН')

        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        asyncio.run(gpn_set_card_states_fn(balance_ids_to_change_card_states))

    else:
        _logger.info('Блокировка / разблокировка карт не требуется: не было транзакций '
                     'с момента последней синхронизации')

    return "COMPLETE"


async def gpn_cards_bind_company_fn(card_ids: List[str], personal_account: str, limit_sum: int | float) -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        gpn = GPNController(session)
        await gpn.gpn_bind_company_to_cards(card_ids, personal_account, limit_sum)

    # Закрываем соединение с БД
    await sessionmanager.close()


@celery.task(name="GPN_CARDS_BIND_COMPANY")
def gpn_cards_bind_company(card_ids: List[str], personal_account: str, limit_sum: int | float) -> None:
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(gpn_cards_bind_company_fn(card_ids, personal_account, limit_sum))


async def gpn_cards_unbind_company_fn(card_ids: List[str]) -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        gpn = GPNController(session)
        await gpn.gpn_unbind_company_from_cards(card_ids)

    # Закрываем соединение с БД
    await sessionmanager.close()


@celery.task(name="GPN_CARD_UNBIND_COMPANY")
def gpn_cards_unbind_company(card_ids: List[str]) -> None:
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(gpn_cards_unbind_company_fn(card_ids))


async def sync_gpn_cards_fn() -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        gpn = GPNController(session)
        await gpn.sync_cards()

    # Закрываем соединение с БД
    await sessionmanager.close()


@celery.task(name="SYNC_GPN_CARDS")
def sync_gpn_cards() -> None:
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(sync_gpn_cards_fn())


async def gpn_issue_virtual_cards_fn(amount: int) -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        gpn_controller = GPNController(session)
        await gpn_controller.issue_virtual_cards(amount)

    # Закрываем соединение с БД
    await sessionmanager.close()


@celery.task(name="GPN_ISSUE_VIRTUAL_CARDS")
def gpn_issue_virtual_cards(amount: int) -> None:
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(gpn_issue_virtual_cards_fn(amount))


@celery.task(name="GPN_SET_CARD_STATE")
def gpn_set_card_state(external_card_id: str, activate: bool) -> None:
    action = "разблокировки" if activate else "блокировки"
    _logger.info(f'Запускаю задачу {action} карты ГПН')
    gpn_api = GPNApi()
    if activate:
        gpn_api.activate_cards([external_card_id])
    else:
        gpn_api.block_cards([external_card_id])


@celery.task(name="GPN_TEST")
def gpn_test() -> None:
    gpn_api = GPNApi()
    # gpn_api.set_card_group_limits([('5287241', 1500000)])
    gpn_api.get_transactions(2)
