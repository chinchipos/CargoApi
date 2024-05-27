import traceback
from typing import Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.connectors.calc_balance import CalcBalance
from src.connectors.khnp.connector import KHNPConnector
from src.connectors.khnp.exceptions import KHNPConnectorError, KHNPParserError
from src.tasks.init import sync_task_logger


async def perform_khnp_operations(session: AsyncSession) -> Dict[str, Any]:
    khnp = KHNPConnector(session)

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
    for company_id, provider_transaction_dt in provider_calc_balance_info.items():
        if global_calc_balance_info.get(company_id, None):
            if provider_transaction_dt < global_calc_balance_info[company_id]:
                global_calc_balance_info[company_id] = provider_transaction_dt

        else:
            global_calc_balance_info[company_id] = provider_transaction_dt


async def run_sync(session: AsyncSession) -> None:
    calc_balance_info = {}

    # Запускаем процедуры синхронизации данных с KHNP
    sync_task_logger.info('Запускаю процедуру синхронизации данных с ННК (KHNP)')
    try:
        khnp_calc_balance_info = await perform_khnp_operations(session)

    except (KHNPConnectorError, KHNPParserError):
        sync_task_logger.info('Синхронизации с ННК (KHNP) завершилась с ошибкой')

    except Exception:
        print(traceback.format_exc())
        sync_task_logger.info('Синхронизации с ННК (KHNP) завершилась с ошибкой')

    else:
        update_calc_balance_info(calc_balance_info, khnp_calc_balance_info)
        sync_task_logger.info('Синхронизации с ННК (KHNP) успешно выполнена')

    # Формируем новую историю баланса организаций
    if calc_balance_info:
        sync_task_logger.info('Формирую новую историю баланса организаций')
        calc_balance = CalcBalance(session)
        await calc_balance.calculate(calc_balance_info)
