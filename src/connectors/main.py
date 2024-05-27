import asyncio
import sys
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.connectors.khnp.connector import KHNPConnector
from src.connectors.khnp.exceptions import KHNPConnectorError, KHNPParserError
from src.database.db import DatabaseSessionManager
from src.main import PROD_URI

sessionmanager = DatabaseSessionManager()
sessionmanager.init(PROD_URI)


async def perform_khnp_operations(session: AsyncSession) -> None:
    try:
        khnp = KHNPConnector(session)

        # Прогружаем наш баланс
        await khnp.load_balance(need_authorization=True)

        # Прогружаем карты
        await khnp.load_cards(need_authorization=False)

        # Прогружаем транзакции
        calculation_info = await khnp.load_transactions(login=False)

    except (KHNPConnectorError, KHNPParserError) as e:
        print(e)

    except Exception as e:
        print(e)


async def main():

    async with sessionmanager.session() as session:
        # Запускаем процедуры синхронизации данных с KHNP
        await perform_khnp_operations(session)

    # if calculation_info:
    #    # Формируем новую историю баланса организации
    #    calc_balance = CalcBalance(session)
    #    await calc_balance.calculate(calculation_info)

    await sessionmanager.close()

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

asyncio.run(main())
