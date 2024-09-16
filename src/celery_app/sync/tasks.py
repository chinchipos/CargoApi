from typing import List

from celery import chain, chord

from src.celery_app.balance.tasks import calc_balances
from src.celery_app.exceptions import CeleryError
from src.celery_app.gpn.tasks import gpn_sync, gpn_update_group_limits
from src.celery_app.group_limit_order import GroupLimitOrder
from src.celery_app.irrelevant_balances import IrrelevantBalances
from src.celery_app.main import celery
from src.celery_app.ops.tasks import ops_sync
from src.utils.enums import System
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
    gpn_sum_deltas = {}
    systems = [
        # System.KHNP,
        System.GPN,
        System.OPS
    ]
    for i, system in enumerate(systems):
        if irrelevant_balances_list[i]:
            irrelevant_balances.extend(irrelevant_balances_list[i])

            # Собираем воедино информацию о балансовых дельтах по транзакциям для выставления групповых лимитов ГПН
            if system != System.GPN:
                for personal_account, delta_sum in irrelevant_balances_list[i]["sum_deltas"].items():
                    if personal_account in gpn_sum_deltas:
                        gpn_sum_deltas[personal_account] += delta_sum
                    else:
                        gpn_sum_deltas[personal_account] = delta_sum

        else:
            messages.append(f"Ошибка синхронизации с {system.value}")

    # Создаем ордера на изменение лимитов ГПН
    gpn_limit_orders = []
    for personal_account, delta_sum in gpn_sum_deltas.items():
        gpn_limit_orders.append(
            GroupLimitOrder(
                personal_account=personal_account,
                delta_sum=delta_sum
            )
        )

    tasks = [
        gpn_update_group_limits.si(gpn_limit_orders),
        calc_balances.si(irrelevant_balances),
        # khnp_set_card_states.s(),
    ]
    if messages:
        tasks.append(fail.si(messages))

    chain(*tasks)()


sync = chord(
    header=[
        # khnp_sync.si(),
        gpn_sync.si(),
        ops_sync.si(),
    ],
    body=after_sync.s()
)
