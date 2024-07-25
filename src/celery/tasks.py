import sys
import traceback
from typing import List

import asyncio

from celery import Celery, chord, chain

from src.celery.card_manager import CardMgr
from src.celery.exceptions import celery_logger
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
async def calc_balances_fn(irrelevant_balances: IrrelevantBalances) -> str:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        cb = CalcBalances(session)
        await cb.calculate(irrelevant_balances, celery_logger)

    # Закрываем соединение с БД
    await sessionmanager.close()

    return "COMPLETE"


@celery.task(name="CALC_BALANCES")
def calc_balances(irrelevant_balances: IrrelevantBalances) -> str:
    if not irrelevant_balances['data']:
        celery_logger.info("Пересчет балансов не требуется")
        return "COMPLETE"
    else:
        celery_logger.info("Пересчитываю балансы")
        try:
            return asyncio.run(calc_balances_fn(irrelevant_balances))
        except Exception as e:
            trace_info = traceback.format_exc()
            celery_logger.error(str(e))
            celery_logger.error(trace_info)
            celery_logger.info('Пересчет балансов завершился с ошибкой')


# Задача пересчета овердрафтов
balance_id_str_type = str


async def calc_overdrafts_fn() -> List[balance_id_str_type]:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        overdraft = Overdraft(session)
        balances_to_block_cards = await overdraft.calculate()

    # Закрываем соединение с БД
    await sessionmanager.close()

    return balances_to_block_cards


@celery.task(name="CALC_OVERDRAFTS")
def calc_overdrafts() -> List[balance_id_str_type]:
    celery_logger.info('Запускаю задачу расчета овердрафтов')

    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    return asyncio.run(calc_overdrafts_fn())


async def block_cards_fn(balances_to_block_cards: List[balance_id_str_type]) -> str:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        pass

    # Закрываем соединение с БД
    await sessionmanager.close()

    return "COMPLETE"


@celery.task(name="BLOCK_CARDS")
def block_cards(balances_to_block_cards: List[balance_id_str_type]) -> str:
    celery_logger.info('Запускаю задачу блокировки карт')

    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    return asyncio.run(block_cards_fn(balances_to_block_cards))


async def block_cards_test_fn(balances_to_block_cards: List[balance_id_str_type]) -> str:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        card_mgr = CardMgr(session=session)
        await card_mgr.activate_cards(balances_to_block_cards)

    # Закрываем соединение с БД
    await sessionmanager.close()

    return "COMPLETE"


@celery.task(name="BLOCK_CARDS_TEST")
def block_cards_test(balances_to_block_cards: List[balance_id_str_type]) -> str:
    celery_logger.info('Запускаю задачу блокировки карт')

    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    return asyncio.run(block_cards_test_fn(balances_to_block_cards))


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
    calc_balances.s()
)


# Цепочка:
# "Расчет овердрафтов" <-> "Блокировка/разблокировка карт"
overdraft_chain = chain(
    calc_overdrafts.si(),
    block_cards.s()
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
