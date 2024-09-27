from typing import List

from celery import chain, chord

from src.celery_app.balance.tasks import calc_balances_chain
from src.celery_app.exceptions import CeleryError
from src.celery_app.gpn.tasks import gpn_sync
from src.celery_app.irrelevant_balances import IrrelevantBalances
from src.celery_app.main import celery
from src.celery_app.ops.tasks import ops_sync
from src.utils.enums import System
from src.utils.loggers import get_logger

_logger = get_logger(name="SYNC_TASKS", filename="celery.log")


@celery.task(name="FAIL")
def fail(messages: List[str]) -> None:
    raise CeleryError(message=", ".join(messages), trace=False)


@celery.task(name="AFTER_SYNC")
def after_sync(irrelevant_balances_list: List[IrrelevantBalances]):
    _logger.info("Агрегирую синхронизационные данные")
    irrelevant_balances = IrrelevantBalances()
    messages = []
    systems = [
        # System.KHNP,
        System.GPN,
        System.OPS
    ]
    for i, system in enumerate(systems):
        if irrelevant_balances_list[i]:
            irrelevant_balances.extend(irrelevant_balances_list[i])

        else:
            messages.append(f"Ошибка синхронизации с {system.value}")

    if messages:
        tasks = [
            calc_balances_chain(irrelevant_balances=irrelevant_balances),
            fail.si(messages)
        ]
        chain(*tasks)()
    else:
        calc_balances_chain(irrelevant_balances=irrelevant_balances)


@celery.task(name="SYNC_WITH_SYSTEMS")
def sync_with_systems() -> None:
    chord(
        header=[
            # khnp_sync.si(),
            gpn_sync.si(),
            ops_sync.si(),
        ],
        body=after_sync.s()
    )()
