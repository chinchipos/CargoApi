import asyncio
import sys
from typing import Dict, List, Any

from src.celery_app.gpn.api import GPNApi
from src.celery_app.gpn.controller import GPNController
from src.celery_app.async_helper import perform_controller_actions
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


async def service_sync_fn() -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        gpn_controller = GPNController(session)
        await gpn_controller.init_system()
        await gpn_controller.service_sync()

    # Закрываем соединение с БД
    await sessionmanager.close()


@celery.task(name="GPN_SERVICE_SYNC")
def gpn_service_sync() -> None:
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(service_sync_fn())


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

    _logger.info(f'Завершена задача {action} карты ГПН')


async def delete_card_limits_fn(limit_ids: List[str]) -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        gpn_controller = GPNController(session)
        await gpn_controller.delete_card_limits(limit_ids)

    # Закрываем соединение с БД
    await sessionmanager.close()


@celery.task(name="GPN_DELETE_CARD_LIMITS")
def gpn_delete_card_limits(limit_ids: List[str]) -> None:
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(delete_card_limits_fn(limit_ids))


# async def create_card_limits_fn(company_id: str, card_external_id: str, limit_ids: List[str]) -> None:
#     sessionmanager = DatabaseSessionManager()
#     sessionmanager.init(PROD_URI)
#
#     async with sessionmanager.session() as session:
#         gpn_controller = GPNController(session)
#         await gpn_controller.set_card_limits(company_id, card_external_id, limit_ids)
#
#     # Закрываем соединение с БД
#     await sessionmanager.close()


# @celery.task(name="GPN_CREATE_CARD_LIMITS")
# def gpn_create_card_limits(company_id: str, card_external_id: str, limit_ids: List[str]) -> None:
#     if sys.platform == 'win32':
#         asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
#
#     asyncio.run(create_card_limits_fn(company_id, card_external_id, limit_ids))


@celery.task(name="GPN_CREATE_CARD_LIMITS")
def gpn_create_card_limits(company_id: str, card_external_id: str, limit_ids: List[str]) -> None:
    _logger.info('Запускаю задачу установки карточного лимита ГПН')
    perform_controller_actions(
        controller_name="GPNController",
        func_name="set_card_limits",
        company_id=company_id,
        card_external_id=card_external_id,
        limit_ids=limit_ids
    )
    _logger.info('Завершена задача установки карточного лимита ГПН')


async def gpn_import_azs_fn() -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        gpn_controller = GPNController(session)
        await gpn_controller.import_azs()

    # Закрываем соединение с БД
    await sessionmanager.close()


@celery.task(name="GPN_IMPORT_AZS")
def gpn_import_azs() -> None:
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(gpn_import_azs_fn())


async def update_group_limits_fn(orders: List[Dict[str, Any]]) -> None:
    if not orders:
        return None

    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        gpn_controller = GPNController(session)
        await gpn_controller.init_system()
        await gpn_controller.update_group_limits(orders=orders)

    # Закрываем соединение с БД
    await sessionmanager.close()


@celery.task(name="GPN_UPDATE_GROUP_LIMITS")
def gpn_update_group_limits(orders: List[Dict[str, Any]]) -> None:
    asyncio.run(update_group_limits_fn(orders))


async def binding_cards_fn(card_numbers: List[str], previous_company_id: str, new_company_id: str) -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        gpn_controller = GPNController(session)
        await gpn_controller.init_system()
        await gpn_controller.binding_cards(card_numbers, previous_company_id, new_company_id)

    # Закрываем соединение с БД
    await sessionmanager.close()


@celery.task(name="GPN_BINDING_CARDS")
def gpn_binding_cards(card_numbers: List[str], previous_company_id: str, new_company_id: str) -> None:
    asyncio.run(binding_cards_fn(card_numbers, previous_company_id, new_company_id))


@celery.task(name="GPN_SYNC_CARD_STATES")
def gpn_sync_card_states() -> None:
    _logger.info('Начинаю синхронизацию состояний карт с ГПН')
    perform_controller_actions(
        controller_name="GPNController",
        func_name="sync_card_states"
    )
    _logger.info('Завершена синхронизация состояний карт с ГПН')


@celery.task(name="GPN_TEST")
def gpn_test() -> None:
    api = GPNApi()
    regions = api.get_regions()
    print(regions)
    # api.set_card_group_limits([('5287241', 1500000)])
    # api.get_transactions(5)
    # product_types = api.get_product_types()
    # groups = api.get_card_groups()
    # for group in groups:
    #     if group['name'] == "5287241":
    #         limits = api.get_card_group_limits(group['id'])
    #         for limit in limits:
    #             print(limit)
    #         break
