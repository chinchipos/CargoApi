from typing import Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.connectors.calc_balance import CalcBalance
from src.connectors.khnp.config import SYSTEM_SHORT_NAME
from src.connectors.khnp.connector import KHNPConnector
from src.connectors.khnp.exceptions import KHNPConnectorError, KHNPParserError
from src.database.models import System
from src.repositories.system import SystemRepository
from src.celery.init import sync_task_logger

import traceback

from src.utils.enums import ContractScheme


async def get_system(session: AsyncSession) -> System:
    system_repository = SystemRepository(session)
    system = await system_repository.get_system_by_short_name(
        system_fhort_name=SYSTEM_SHORT_NAME,
        scheme=ContractScheme.OVERBOUGHT
    )
    return system


async def perform_khnp_operations(session: AsyncSession) -> Dict[str, Any]:
    system = await get_system(session)
    khnp = KHNPConnector(session, system)

    # Прогружаем наш баланс
    await khnp.load_balance(need_authorization=True)

    # Прогружаем карты
    await khnp.load_cards(need_authorization=False)

    # Прогружаем транзакции
    calc_balance_info = await khnp.load_transactions(need_authorization=False)
    return calc_balance_info


def update_calc_balance_info(
    global_calc_balance_info: Dict[str, Any],
    provider_calc_balance_info: Dict[str, Any]
) -> None:
    for balance_id, provider_transaction_dt in provider_calc_balance_info.items():
        if global_calc_balance_info.get(balance_id, None):
            if provider_transaction_dt < global_calc_balance_info[balance_id]:
                global_calc_balance_info[balance_id] = provider_transaction_dt

        else:
            global_calc_balance_info[balance_id] = provider_transaction_dt


async def run_sync(session: AsyncSession) -> None:
    calc_balance_info = {}

    # Запускаем процедуры синхронизации данных с KHNP
    sync_task_logger.info('Запускаю процедуру синхронизации данных с ННК (KHNP)')
    try:
        khnp_calc_balance_info = await perform_khnp_operations(session)

    except (KHNPConnectorError, KHNPParserError):
        sync_task_logger.info('Синхронизации с ННК (KHNP) завершилась с ошибкой')

    except Exception as e:
        trace_info = traceback.format_exc()
        sync_task_logger.error(str(e))
        sync_task_logger.error(trace_info)
        sync_task_logger.info('Синхронизации с ННК (KHNP) завершилась с ошибкой')

    else:
        update_calc_balance_info(calc_balance_info, khnp_calc_balance_info)
        sync_task_logger.info('Синхронизации с ННК (KHNP) успешно выполнена')

    # Формируем новую историю баланса организаций
    if calc_balance_info:
        sync_task_logger.info('Формирую новую историю баланса организаций')
        calc_balance = CalcBalance(session)
        await calc_balance.calculate(calc_balance_info)
