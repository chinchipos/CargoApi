import asyncio
import sys

from src.celery_app.async_helper import perform_controller_actions
from src.celery_app.irrelevant_balances import IrrelevantBalances
from src.celery_app.ops.controller import OpsController
from src.celery_app.main import celery
from src.config import PROD_URI
from src.database.db import DatabaseSessionManager
from src.utils.loggers import get_logger

_logger = get_logger(name="OPS_TASKS", filename="celery.log")


# async def ops_sync_fn() -> IrrelevantBalances:
#     sessionmanager = DatabaseSessionManager()
#     sessionmanager.init(PROD_URI)
#
#     async with sessionmanager.session() as session:
#         ops_controller = OpsController(session)
#         await ops_controller.init_system()
#         irrelevant_balances = await ops_controller.sync()
#
#     # Закрываем соединение с БД
#     await sessionmanager.close()
#
#     _logger.info('Синхронизация с ОПС успешно завершена')
#     return irrelevant_balances
#
#
# @celery.task(name="OPS_SYNC")
# def ops_sync() -> IrrelevantBalances:
#     _logger.info("Запускаю синхронизацию с ОПС")
#     try:
#         return asyncio.run(ops_sync_fn())
#
#     except Exception as e:
#         _logger.exception(str(e))
#         _logger.info("Ошибка синхронизации с ОПС")


@celery.task(name="SYNC_GPN")
def gpn_sync() -> IrrelevantBalances:
    _logger.info("Запускаю синхронизацию с ОПС")
    try:
        irrelevant_balances = perform_controller_actions(
            controller_name="OpsController",
            func_name="sync"
        )
        _logger.info("Завершена синхронизация с ОПС")
        return irrelevant_balances

    except Exception as e:
        _logger.exception(str(e))
        _logger.info("Ошибка синхронизации с ОПС")


async def ops_import_dicts_fn() -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        ops_controller = OpsController(session)
        await ops_controller.init_system()

        # _logger.info('Импорт карт...')
        # await ops_controller.load_cards()
        # _logger.info('Выполнено')

        _logger.info('Импорт АЗС и терминалов...')
        await ops_controller.load_azs()
        _logger.info('Выполнено')

        # api = OpsApi()
        # api.export_transactions()

        # _logger.info('Импорт продуктов...')
        # await ops_controller.load_goods()
        # _logger.info('Выполнено')

    # Закрываем соединение с БД
    await sessionmanager.close()


@celery.task(name="OPS_IMPORT_DICTS")
def ops_import_dicts() -> None:
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(ops_import_dicts_fn())


async def set_azs_tariffs_fn() -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        ops_controller = OpsController(session)
        await ops_controller.init_system()

        _logger.info('Импорт начался')
        await ops_controller.import_ops_stations_from_excel()
        _logger.info('Импорт завершен')

    # Закрываем соединение с БД
    await sessionmanager.close()


@celery.task(name="OPS_SET_AZS_TARIFFS")
def ops_set_azs_tariffs() -> None:
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(set_azs_tariffs_fn())
