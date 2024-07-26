import asyncio
import sys
import traceback
from typing import List

from celery import Celery, chord, chain

from src.celery.card_manager import CardMgr
from src.celery.exceptions import celery_logger, CeleryError
from src.celery.overdraft import Overdraft
from src.config import PROD_URI
from src.connectors.calc_balance import CalcBalances
from src.connectors.irrelevant_balances import IrrelevantBalances
from src.connectors.khnp.connector import KHNPConnector
from src.database.db import DatabaseSessionManager

redis_server = 'redis://localhost:6379'
sa_result_backend = (PROD_URI.replace("postgresql+psycopg", "db+postgresql") +
                     "?sslmode=verify-full&target_session_attrs=read-write")
celery = Celery('cargonomica', backend=sa_result_backend, broker=f'{redis_server}/0')
celery.conf.broker_connection_retry_on_startup = True
celery.conf.broker_connection_max_retries = 10
celery.conf.timezone = 'Europe/Moscow'


# ХНП
async def sync_khnp_fn() -> IrrelevantBalances:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        khnp = KHNPConnector(session)
        await khnp.init_system()
        irrelevant_balances = await khnp.sync()

    # Закрываем соединение с БД
    await sessionmanager.close()
    celery_logger.info('Синхронизация с ХНП успешно завершена')
    return irrelevant_balances


@celery.task(name="SYNC_KHNP")
def sync_khnp() -> IrrelevantBalances:
    celery_logger.info("Запускаю синхронизацию с ХНП")
    return asyncio.run(sync_khnp_fn())


# Noname - методы, в которые можно будет добавить новую систему
async def sync_noname_fn() -> IrrelevantBalances:
    celery_logger.info('Синхронизация с Noname успешно завершена')
    return IrrelevantBalances()


@celery.task(name="SYNC_NONAME")
def sync_noname() -> IrrelevantBalances:
    celery_logger.info("Запускаю синхронизацию с Noname")
    return asyncio.run(sync_noname_fn())


# Агрегирование результатов после синхронизации со всеми системами
@celery.task(name="AGREGATE_SYNC_SYSTEMS_DATA")
def agregate_sync_systems_data(irrelevant_balances_list: List[IrrelevantBalances]) -> IrrelevantBalances:
    celery_logger.info("Агрегирую синхонизационные данные")
    irrelevant_balances = IrrelevantBalances()
    for ib in irrelevant_balances_list:
        irrelevant_balances.extend(ib['data'])

    return irrelevant_balances


# Задача пересчета балансов
balance_id_str_type = str
balances_to_block_cards_type = List[balance_id_str_type]
balances_to_activate_cards_type = List[balance_id_str_type]


async def calc_balances_fn(irrelevant_balances: IrrelevantBalances) -> None:

    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        cb = CalcBalances(session)
        await cb.calculate(irrelevant_balances, celery_logger)

    # Закрываем соединение с БД
    await sessionmanager.close()


@celery.task(name="CALC_BALANCES")
def calc_balances(irrelevant_balances: IrrelevantBalances) -> bool:

    if not irrelevant_balances['data']:
        celery_logger.info("Пересчет балансов не требуется")
        return False

    else:
        celery_logger.info("Пересчитываю балансы")
        try:
            asyncio.run(calc_balances_fn(irrelevant_balances))
            return True

        except Exception as e:
            trace_info = traceback.format_exc()
            celery_logger.error(str(e))
            celery_logger.error(trace_info)
            error = 'Пересчет балансов завершился ошибкой. См лог.'
            celery_logger.info(error)
            raise CeleryError(message=error)


async def block_or_activate_cards_fn() -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        card_mgr = CardMgr(session=session)
        await card_mgr.block_or_activate_cards()

    # Закрываем соединение с БД
    await sessionmanager.close()


@celery.task(name="BLOCK_OR_ACTIVATE_CARDS")
def block_or_activate_cards(run_required: bool) -> str:
    if run_required:
        celery_logger.info('Запускаю задачу блокировки / разблокировки карт')

        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        asyncio.run(block_or_activate_cards_fn())

    else:
        celery_logger.info('Блокировка / разблокировка карт не требуется: '
                           'не было транзакций с момента последней синхронизации')

    return "COMPLETE"


# Задача пересчета овердрафтов
async def calc_overdrafts_fn() -> bool:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        overdraft = Overdraft(session)
        await overdraft.calculate()

    # Закрываем соединение с БД
    await sessionmanager.close()

    return True


@celery.task(name="CALC_OVERDRAFTS")
def calc_overdrafts() -> bool:
    celery_logger.info('Запускаю задачу расчета овердрафтов')

    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    return asyncio.run(calc_overdrafts_fn())


# Модель запуска цепочек задач.

# Этапы последовательного выполнения:
# 1. Синхронизация (прогружаем наш баланс, карты, транзакции).
# 2. Пересчет овердрафтов за период
# 3. Пересчет балансов за период

# Агрегирование цепочек "Синхронизация карт" <-> "Синхронизация транзакций"
sync_systems = chord(
    header=[
        sync_khnp.si(),
        sync_noname.si()
    ],
    body=agregate_sync_systems_data.s()
)


# Цепочка:
# "Агрегация (карты-транзакции)" <-> "Пересчет балансов" <-> "Блокировка/разблокировка карт"
sync_chain = chain(
    sync_systems,
    calc_balances.s(),
    block_or_activate_cards.s()
)


# Цепочка:
# "Расчет овердрафтов" <-> "Блокировка/разблокировка карт"
overdraft_chain = chain(
    calc_overdrafts.si(),
    block_or_activate_cards.s()
)


def run_sync_systems():
    celery_logger.info('Запускаю задачу синхронизации с системами поставщиков')

    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    sync_chain()


def run_calc_overdrafts():
    celery_logger.info('Запускаю задачу рачсета овердрафтов')

    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    overdraft_chain()
