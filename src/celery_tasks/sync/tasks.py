from typing import List, Dict

from celery import chain, chord, shared_task, group

from src.celery_tasks.exceptions import celery_logger
from src.celery_tasks.gpn.tasks import gpn_sync, gpn_set_card_states
from src.celery_tasks.limits.tasks import set_card_group_limit
from src.celery_tasks.khnp.tasks import khnp_sync, khnp_set_card_states
from src.celery_tasks.balance.tasks import calc_balances
from src.celery_tasks.main import celery
from src.celery_tasks.irrelevant_balances import IrrelevantBalances


@celery.task(name="AGREGATE_SYNC_SYSTEMS_DATA")
def agregate_sync_systems_data(irrelevant_balances_list: List[IrrelevantBalances]) -> IrrelevantBalances:
    celery_logger.info("Агрегирую синхронизационные данные")
    irrelevant_balances = IrrelevantBalances()
    for ib in irrelevant_balances_list:
        irrelevant_balances.extend(ib['data'])

    return irrelevant_balances


# Этапы последовательного выполнения:
# 1. Синхронизация (прогружаем наш баланс, карты, транзакции).
# 2. Пересчет балансов за период
# 3. Выставление статусов картам

load_balance_card_transactions = chord(
    header=[
        khnp_sync.si(),
        gpn_sync.si()
    ],
    body=agregate_sync_systems_data.s()
)


@shared_task
def set_card_states(balance_ids: Dict[str, List[str]]):
    balance_ids_list = list(balance_ids["to_block"])
    balance_ids_list.extend(balance_ids["to_activate"])
    grouped_tasks = group(
        khnp_set_card_states.s(balance_ids),
        gpn_set_card_states.s(balance_ids),
        set_card_group_limit.s(balance_ids_list)
    )
    return grouped_tasks()


sync_chain = chain(
    load_balance_card_transactions,
    calc_balances.s(),
    set_card_states.s()
)
