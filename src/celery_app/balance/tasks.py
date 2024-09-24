import asyncio
import sys
from datetime import datetime
from typing import Dict, List, Any

from celery import chain

from src.celery_app.async_helper import perform_controller_actions
from src.celery_app.balance.calc_balance import CalcBalances
from src.celery_app.gpn.tasks import gpn_update_group_limits
from src.celery_app.irrelevant_balances import IrrelevantBalances
from src.celery_app.main import celery
from src.config import PROD_URI
from src.database.db import DatabaseSessionManager
from src.utils.enums import System
from src.utils.loggers import get_logger

_logger = get_logger(name="BALANCE_TASKS", filename="celery.log")


# async def calc_balances_fn(irrelevant_balances: IrrelevantBalances) -> Dict[str, List[str]]:
#
#     sessionmanager = DatabaseSessionManager()
#     sessionmanager.init(PROD_URI)
#
#     async with sessionmanager.session() as session:
#         cb = CalcBalances(session)
#         balance_ids_to_change_card_states = await cb.calculate(irrelevant_balances)
#
#     # Закрываем соединение с БД
#     await sessionmanager.close()
#     return balance_ids_to_change_card_states


# @celery.task(name="CALC_BALANCES")
# def calc_balances(irrelevant_balances: IrrelevantBalances) -> Dict[str, List[str]]:
#     if not irrelevant_balances['irrelevant_balances']:
#         _logger.info("Пересчет балансов не требуется")
#         return {"to_block": [], "to_activate": []}
#
#     else:
#         _logger.info("Пересчитываю балансы")
#         balance_ids_to_change_card_states = asyncio.run(calc_balances_fn(irrelevant_balances))
#         _logger.info("Пересчет балансов выполнен")
#         return balance_ids_to_change_card_states


@celery.task(name="CALC_BALANCES")
def calc_balances(irrelevant_balances: IrrelevantBalances) -> Dict[str, List[str]]:
    if not irrelevant_balances['irrelevant_balances']:
        _logger.info("Пересчет балансов не требуется")
        return {"to_block": [], "to_activate": []}

    else:
        _logger.info("Пересчитываю балансы")
        balance_ids_to_change_card_states = perform_controller_actions(
            controller_name="CalcBalances",
            func_name="calculate",
            irrelevant_balances=irrelevant_balances
        )
        _logger.info("Пересчет балансов выполнен")
        return balance_ids_to_change_card_states


async def recalculate_transactions_fn(from_date_time: datetime, personal_accounts: List[str] | None) \
        -> Dict[str, Any]:

    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        cb = CalcBalances(session)
        systems_dict = await cb.recalculate_transactions(from_date_time, personal_accounts)

    # Закрываем соединение с БД
    await sessionmanager.close()
    return systems_dict


@celery.task(name="RECALCULATE_TRANSACTIONS")
def recalculate_transactions(from_date_time: datetime, personal_accounts: List[str] | None = None) -> None:
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    systems_dict = asyncio.run(recalculate_transactions_fn(from_date_time, personal_accounts))

    gpn_sum_deltas = {}
    for system_id, data in systems_dict.items():
        if data["system_name"] != System.GPN:
            for personal_account, delta_sum in data["irrelevant_balances"]["total_sum_deltas"].items():
                if personal_account in gpn_sum_deltas:
                    gpn_sum_deltas[personal_account] += delta_sum
                else:
                    gpn_sum_deltas[personal_account] = delta_sum

    # Создаем ордера на изменение лимитов ГПН
    # gpn_limit_orders = []
    # for personal_account, delta_sum in gpn_sum_deltas.items():
    #     gpn_limit_orders.append(
    #         GroupLimitOrder(
    #             personal_account=personal_account,
    #             delta_sum=delta_sum
    #         )
    #     )

    irrelevant_balances = None
    for system_id, data in systems_dict.items():
        irrelevant_balances = data["irrelevant_balances"]
        break

    calc_balances_chain(
        irrelevant_balances=irrelevant_balances,
        gpn_group_limit_deltas=gpn_sum_deltas
    )


personal_account_str = str
delta_sum_float = float


@celery.task(name="CALC_BALANCES_CHAIN")
def calc_balances_chain(irrelevant_balances: IrrelevantBalances,
                        gpn_group_limit_increase_deltas: Dict[personal_account_str, List[delta_sum_float]],
                        gpn_group_limit_decrease_deltas: Dict[personal_account_str, List[delta_sum_float]]) \
        -> None:
    tasks = [
        calc_balances.si(irrelevant_balances),
        gpn_update_group_limits.si(gpn_group_limit_increase_deltas, gpn_group_limit_decrease_deltas)
    ]
    chain(*tasks)()
