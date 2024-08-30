from typing import List

from celery import chain, chord

from src.celery_app.balance.tasks import calc_balances
from src.celery_app.exceptions import CeleryError
from src.celery_app.gpn.tasks import gpn_sync
from src.celery_app.irrelevant_balances import IrrelevantBalances
from src.celery_app.khnp.tasks import khnp_sync, khnp_set_card_states
from src.celery_app.limits.tasks import gpn_set_card_group_limit
from src.celery_app.main import celery
from src.utils.loggers import get_logger

_logger = get_logger(name="SYNC_TASKS", filename="celery.log")


@celery.task(name="FAIL")
def fail(messages: List[str]) -> None:
    raise CeleryError(message=" ".join(messages), trace=False)


@celery.task(name="AFTER_SYNC")
def after_sync(irrelevant_balances_list: List[IrrelevantBalances]):
    _logger.info("Агрегирую синхронизационные данные")
    irrelevant_balances = IrrelevantBalances()
    messages = []

    if irrelevant_balances_list[0]:
        irrelevant_balances.extend(irrelevant_balances_list[0])
    else:
        messages.append("Ошибка синхронизации с ХНП.")

    if irrelevant_balances_list[1]:
        irrelevant_balances.extend(irrelevant_balances_list[1])
    else:
        messages.append("Ошибка синхронизации с ГПН.")

    changed_balances = [balance_id for balance_id in irrelevant_balances.data().keys()]
    tasks = [
        calc_balances.si(irrelevant_balances),
        khnp_set_card_states.s(),
        gpn_set_card_group_limit.si(changed_balances)
    ]
    if messages:
        tasks.append(fail.si(messages))

    chain(*tasks)()


sync = chord(
    header=[
        khnp_sync.si(),
        gpn_sync.si()
    ],
    body=after_sync.s()
)
