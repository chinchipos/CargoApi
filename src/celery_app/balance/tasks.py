import asyncio
from typing import Dict, List

from src.celery_app.balance.calc_balance import CalcBalances
from src.celery_app.irrelevant_balances import IrrelevantBalances
from src.celery_app.main import celery
from src.config import PROD_URI
from src.database.db import DatabaseSessionManager
from src.utils.loggers import get_logger

_logger = get_logger(name="BALANCE_TASKS", filename="celery.log")


async def calc_balances_fn(irrelevant_balances: IrrelevantBalances) -> Dict[str, List[str]]:

    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        cb = CalcBalances(session)
        balance_ids_to_change_card_states = await cb.calculate(irrelevant_balances)

    # Закрываем соединение с БД
    await sessionmanager.close()
    return balance_ids_to_change_card_states


@celery.task(name="CALC_BALANCES")
def calc_balances(irrelevant_balances: IrrelevantBalances) -> Dict[str, List[str]]:
    if not irrelevant_balances['irrelevant_balances']:
        _logger.info("Пересчет балансов не требуется")
        return {"to_block": [], "to_activate": []}

    else:
        _logger.info("Пересчитываю балансы")
        return asyncio.run(calc_balances_fn(irrelevant_balances))
