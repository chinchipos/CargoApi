import asyncio
import sys
import traceback
from typing import Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.connectors.calc_balance import CalcBalance
from src.connectors.khnp.connector import KHNPConnector
from src.connectors.khnp.exceptions import KHNPConnectorError, KHNPParserError
from src.database.db import DatabaseSessionManager
from src.main import PROD_URI

sessionmanager = DatabaseSessionManager()
sessionmanager.init(PROD_URI)


async def perform_khnp_operations(session: AsyncSession) -> Dict[str, Any]:
        khnp = KHNPConnector(session)

        # Прогружаем наш баланс
        await khnp.load_balance(need_authorization=True)

        # Прогружаем карты
        await khnp.load_cards(need_authorization=False)

        # Прогружаем транзакции
        calc_balance_info = await khnp.load_transactions(need_authorization=False)
        return calc_balance_info
        #return {}


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


async def main():
    calc_balance_info = {}

    async with sessionmanager.session() as session:
        # Запускаем процедуры синхронизации данных с KHNP
        try:
            khnp_calc_balance_info = await perform_khnp_operations(session)

        except (KHNPConnectorError, KHNPParserError) as e:
            pass

        except Exception:
            print(traceback.format_exc())

        else:
            update_calc_balance_info(calc_balance_info, khnp_calc_balance_info)

    # Формируем новую историю баланса организаций
    if calc_balance_info:
        calc_balance = CalcBalance(session)
        await calc_balance.calculate(calc_balance_info)

    await sessionmanager.close()

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

asyncio.run(main())
