import asyncio
import traceback
from typing import Dict, List

from src.celery_tasks.exceptions import celery_logger, CeleryError
from src.celery_tasks.main import celery
from src.celery_tasks.irrelevant_balances import IrrelevantBalances
from src.database.db import DatabaseSessionManager
from src.config import PROD_URI
from src.celery_tasks.balance.calc_balance import CalcBalances


async def calc_balances_fn(irrelevant_balances: IrrelevantBalances) -> Dict[str, List[str]]:

    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        cb = CalcBalances(session)
        balance_ids_to_change_card_states = await cb.calculate(irrelevant_balances, celery_logger)

    # Закрываем соединение с БД
    await sessionmanager.close()
    return balance_ids_to_change_card_states


@celery.task(name="CALC_BALANCES")
def calc_balances(irrelevant_balances: IrrelevantBalances) -> Dict[str, List[str]] | None:
    if not irrelevant_balances['data']:
        celery_logger.info("Пересчет балансов не требуется")
        return {"to_block": [], "to_activate": []}

    else:
        celery_logger.info("Пересчитываю балансы")
        try:
            return asyncio.run(calc_balances_fn(irrelevant_balances))

        except Exception as e:
            trace_info = traceback.format_exc()
            celery_logger.error(str(e))
            celery_logger.error(trace_info)
            error = 'Пересчет балансов завершился ошибкой. См лог.'
            celery_logger.info(error)
            raise CeleryError(message=error)
