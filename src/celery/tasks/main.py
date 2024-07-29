import asyncio
import sys
import traceback
from typing import List

from celery import Celery, chord
from celery import chain

from src.celery.exceptions import celery_logger, CeleryError
from src.celery.tasks.modules.overdrafts import calc_overdrafts_fn, block_or_activate_cards_fn
from src.celery.tasks.modules.sync_systems import sync_khnp_fn, sync_noname_fn, calc_balances_fn
from src.config import PROD_URI
from src.connectors.irrelevant_balances import IrrelevantBalances

redis_server = 'redis://localhost:6379'
sa_result_backend = (PROD_URI.replace("postgresql+psycopg", "db+postgresql") +
                     "?sslmode=verify-full&target_session_attrs=read-write")

celery = Celery('cargonomica', backend=sa_result_backend, broker=f'{redis_server}/0')
celery.conf.broker_connection_retry_on_startup = True
celery.conf.broker_connection_max_retries = 10
celery.conf.timezone = 'Europe/Moscow'


@celery.task(name="SYNC_KHNP")
def sync_khnp() -> IrrelevantBalances:
    celery_logger.info("Запускаю синхронизацию с ХНП")
    return asyncio.run(sync_khnp_fn())


@celery.task(name="SYNC_NONAME")
def sync_noname() -> IrrelevantBalances:
    celery_logger.info("Запускаю синхронизацию с Noname")
    return asyncio.run(sync_noname_fn())


@celery.task(name="CALC_BALANCES")
def calc_balances(irrelevant_balances: IrrelevantBalances) -> bool:

    if not irrelevant_balances['data']:
        celery_logger.info("Пересчет балансов не требуется")
        return True

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


# Агрегирование результатов после синхронизации со всеми системами
@celery.task(name="AGREGATE_SYNC_SYSTEMS_DATA")
def agregate_sync_systems_data(irrelevant_balances_list: List[IrrelevantBalances]) -> IrrelevantBalances:
    celery_logger.info("Агрегирую синхонизационные данные")
    irrelevant_balances = IrrelevantBalances()
    for ib in irrelevant_balances_list:
        irrelevant_balances.extend(ib['data'])

    return irrelevant_balances


@celery.task(name="CALC_OVERDRAFTS")
def calc_overdrafts() -> IrrelevantBalances:

    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    return asyncio.run(calc_overdrafts_fn())


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


# Задача пересчета балансов
balance_id_str_type = str
balances_to_block_cards_type = List[balance_id_str_type]
balances_to_activate_cards_type = List[balance_id_str_type]

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


def run_sync_systems():
    celery_logger.info('Запускаю задачу синхронизации с системами поставщиков')

    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    sync_chain()


# Цепочка:
# "Расчет овердрафтов" <-> "Блокировка/разблокировка карт"
overdraft_chain = chain(
    calc_overdrafts.si(),
    calc_balances.s(),
    block_or_activate_cards.s()
)


def run_calc_overdrafts():
    celery_logger.info('Запускаю задачу рачсета овердрафтов')

    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    overdraft_chain()
