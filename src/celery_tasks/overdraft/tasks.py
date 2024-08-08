import asyncio
import sys

from celery import chain, shared_task, group

from src.celery_tasks.exceptions import celery_logger
from src.celery_tasks.main import celery
from src.celery_tasks.balance.tasks import calc_balances
from src.celery_tasks.overdraft.controller import Overdraft
from src.celery_tasks.gpn.tasks import gpn_set_card_states
from src.celery_tasks.khnp.tasks import khnp_set_card_states
from src.config import PROD_URI
from src.celery_tasks.irrelevant_balances import IrrelevantBalances
from src.database.db import DatabaseSessionManager


async def calc_overdrafts_fn() -> IrrelevantBalances:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        overdraft = Overdraft(session, celery_logger)
        irrelevant_balances = await overdraft.calculate()

    # Закрываем соединение с БД
    await sessionmanager.close()

    return irrelevant_balances


@celery.task(name="CALC_OVERDRAFTS")
def calc_overdrafts() -> IrrelevantBalances:

    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    return asyncio.run(calc_overdrafts_fn())


async def send_overdrafts_report_fn() -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        overdraft = Overdraft(session, celery_logger)
        await overdraft.send_overdrafts_report()

    # Закрываем соединение с БД
    await sessionmanager.close()


@celery.task(name="SEND_OVERDRAFTS_REPORT")
def send_overdrafts_report() -> str:
    celery_logger.info('Запускаю задачу рассылки отчетов по открытым овердрафтам')
    asyncio.run(send_overdrafts_report_fn())
    return "COMPLETE"


@shared_task(name="SET_CARD_STATES")
def set_card_states(result):
    grouped_tasks = group(
        khnp_set_card_states.s(result),
        gpn_set_card_states.s(result)
    )
    return grouped_tasks()


overdraft_chain = chain(
    calc_overdrafts.si(),
    calc_balances.s(),
    set_card_states.s()
)
