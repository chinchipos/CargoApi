import asyncio
import sys

from src.celery_app.irrelevant_balances import IrrelevantBalances
from src.celery_app.ops.controller import OpsController
from src.celery_app.main import celery
from src.config import PROD_URI
from src.database.db import DatabaseSessionManager
from src.utils.loggers import get_logger

_logger = get_logger(name="OPS_TASKS", filename="celery.log")


async def ops_sync_fn() -> IrrelevantBalances:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        ops_controller = OpsController(session)
        await ops_controller.init_system()
        irrelevant_balances = await ops_controller.sync()

    # Закрываем соединение с БД
    await sessionmanager.close()

    _logger.info('Синхронизация с ОПС успешно завершена')
    return irrelevant_balances


@celery.task(name="OPS_SYNC")
def ops_sync() -> IrrelevantBalances:
    _logger.info("Запускаю синхронизацию с ОПС")
    try:
        return asyncio.run(ops_sync_fn())

    except Exception as e:
        _logger.exception(str(e))
        _logger.info("Ошибка синхронизации с ОПС")
