import asyncio
import sys

from celery import chain, shared_task, group

from src.celery_app.main import celery
from src.celery_app.balance.tasks import calc_balances
from src.celery_app.overdraft.controller import Overdraft
from src.celery_app.gpn.tasks import gpn_set_card_states
from src.celery_app.khnp.tasks import khnp_set_card_states
from src.config import PROD_URI
from src.celery_app.irrelevant_balances import IrrelevantBalances
from src.database.db import DatabaseSessionManager
from src.utils.loggers import get_logger

_logger = get_logger(name="OVERDRAFT", filename="celery.log")


async def calc_overdrafts_fn() -> IrrelevantBalances:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        overdraft = Overdraft(session)
        irrelevant_balances = await overdraft.calculate()

    # Закрываем соединение с БД
    await sessionmanager.close()

    return irrelevant_balances


@celery.task(name="CALC_OVERDRAFTS")
def calc_overdrafts() -> IrrelevantBalances:
    _logger.info('Запускаю задачу раcчета овердрафтов')

    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    irrelevant_balances = asyncio.run(calc_overdrafts_fn())
    _logger.info('Раcчет овердрафтов выполнен')
    return irrelevant_balances


async def send_overdrafts_report_fn() -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        overdraft = Overdraft(session)
        await overdraft.send_overdrafts_report()

    # Закрываем соединение с БД
    await sessionmanager.close()


@celery.task(name="OVERDRAFTS_REPORT")
def overdrafts_report() -> str:
    _logger.info('Запускаю задачу рассылки отчетов по овердрафтам')
    asyncio.run(send_overdrafts_report_fn())
    _logger.info('Рассылка отчетов по овердрафтам выполнена')
    return "COMPLETE"


@shared_task(name="SET_CARD_STATES")
def set_card_states(result):
    grouped_tasks = group(
        khnp_set_card_states.s(result),
        gpn_set_card_states.s(result)
    )
    return grouped_tasks()


overdrafts_calc = chain(
    calc_overdrafts.si(),
    calc_balances.s(),
    set_card_states.s()
)
