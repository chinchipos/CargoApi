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
    gpn_increase_sum_deltas = {}
    gpn_decrease_sum_deltas = {}
    systems = [
        # System.KHNP,
        System.GPN,
        # System.OPS
    ]
    for i, system in enumerate(systems):
        if irrelevant_balances_list[i]:
            irrelevant_balances.extend(irrelevant_balances_list[i])

            # Собираем воедино информацию о балансовых дельтах по транзакциям для выставления групповых лимитов ГПН
            if system == System.GPN:
                increase_dict = irrelevant_balances_list[i]["increasing_discount_fee_sum_deltas"]
                for personal_account, delta_sum_list in increase_dict.items():
                    if personal_account in gpn_increase_sum_deltas:
                        gpn_increase_sum_deltas[personal_account].extend(delta_sum_list)
                    else:
                        gpn_increase_sum_deltas[personal_account] = delta_sum_list

                decrease_dict = irrelevant_balances_list[i]["decreasing_discount_fee_sum_deltas"]
                for personal_account, delta_sum_list in decrease_dict.items():
                    if personal_account in gpn_decrease_sum_deltas:
                        gpn_decrease_sum_deltas[personal_account].extend(delta_sum_list)
                    else:
                        gpn_decrease_sum_deltas[personal_account] = delta_sum_list

            else:
                increase_dict = irrelevant_balances_list[i]["increasing_total_sum_deltas"]
                for personal_account, delta_sum_list in increase_dict.items():
                    if personal_account in gpn_increase_sum_deltas:
                        gpn_increase_sum_deltas[personal_account].extend(delta_sum_list)
                    else:
                        gpn_increase_sum_deltas[personal_account] = [delta_sum_list]

                decrease_dict = irrelevant_balances_list[i]["decreasing_total_sum_deltas"]
                for personal_account, delta_sum_list in decrease_dict.items():
                    if personal_account in gpn_decrease_sum_deltas:
                        gpn_decrease_sum_deltas[personal_account].extend(delta_sum_list)
                    else:
                        gpn_decrease_sum_deltas[personal_account] = [delta_sum_list]

        else:
            messages.append(f"Ошибка синхронизации с {system.value}")

    if messages:
        tasks = [
            calc_balances_chain(
                irrelevant_balances=irrelevant_balances,
                gpn_group_limit_increase_deltas=gpn_increase_sum_deltas,
                gpn_group_limit_decrease_deltas=gpn_decrease_sum_deltas
            ),
            fail.si(messages)
        ]
        chain(*tasks)()
    else:
        calc_balances_chain(
            irrelevant_balances=irrelevant_balances,
            gpn_group_limit_increase_deltas=gpn_increase_sum_deltas,
            gpn_group_limit_decrease_deltas=gpn_decrease_sum_deltas
        )


@celery.task(name="SYNC_WITH_SYSTEMS")
def sync_with_systems() -> None:
    chord(
        header=[
            # khnp_sync.si(),
            gpn_sync.si(),
            # ops_sync.si(),
        ],
        body=after_sync.s()
    )()
