from src.celery.exceptions import celery_logger
from src.config import PROD_URI
from src.celery.calc_balance import CalcBalances
from src.connectors.gazpromneft.connector import GPNConnector
from src.connectors.irrelevant_balances import IrrelevantBalances
from src.connectors.khnp.connector import KHNPConnector
from src.database.db import DatabaseSessionManager


async def sync_khnp_fn() -> IrrelevantBalances:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        khnp = KHNPConnector(session, celery_logger)
        await khnp.init_system()
        irrelevant_balances = await khnp.sync()

    # Закрываем соединение с БД
    await sessionmanager.close()
    celery_logger.info('Синхронизация с ХНП успешно завершена')
    return irrelevant_balances


async def sync_gpn_fn() -> IrrelevantBalances:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        gpn = GPNConnector(session, celery_logger)
        await gpn.init_system()
        irrelevant_balances = await gpn.sync()

    # Закрываем соединение с БД
    await sessionmanager.close()
    celery_logger.info('Синхронизация с ГПН успешно завершена')
    return irrelevant_balances


async def calc_balances_fn(irrelevant_balances: IrrelevantBalances) -> None:

    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        cb = CalcBalances(session)
        await cb.calculate(irrelevant_balances, celery_logger)

    # Закрываем соединение с БД
    await sessionmanager.close()
