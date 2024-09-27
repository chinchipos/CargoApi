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
from src.utils.loggers import get_logger

_logger = get_logger(name="BALANCE_TASKS", filename="celery.log")


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

    irrelevant_balances = None
    for system_id, data in systems_dict.items():
        irrelevant_balances = data["irrelevant_balances"]
        break

    calc_balances_chain(
        irrelevant_balances=irrelevant_balances,
        personal_accounts=personal_accounts
    )


personal_account_str = str
delta_sum_float = float


@celery.task(name="CALC_BALANCES_CHAIN")
def calc_balances_chain(irrelevant_balances: IrrelevantBalances, personal_accounts: List[str] | None = None) \
        -> None:
    _personal_accounts = personal_accounts if personal_accounts else irrelevant_balances["personal_accounts"]
    tasks = [
        calc_balances.si(irrelevant_balances),
        gpn_update_group_limits.si(_personal_accounts)
    ]
    chain(*tasks)()
