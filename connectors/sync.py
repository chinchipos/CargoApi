from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from connectors.khnp.sync import KHNPSync
from connectors.calc_balance import CalcBalance
from src.database.db import DatabaseSessionManager
import asyncio

from src.main import PROD_URI

sessionmanager = DatabaseSessionManager()
sessionmanager.init(PROD_URI)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with sessionmanager.session() as session:
        yield session


async def main():

    # Создаем соединение с БД
    session = get_session()

    # Запускаем процедуры синхронизации данных с KHNP
    khnp = KHNPSync(session)
    await khnp.init()

    # Прогружаем наш баланс
    await khnp.load_balance(login=True)

    # Прогружаем карты
    await khnp.load_cards(login=False)

    # Прогружаем транзакции
    calculation_info = await khnp.load_transactions(login=False)

    if calculation_info:
        # Формируем новую историю баланса организации
        calc_balance = CalcBalance(session)
        await calc_balance.calculate(calculation_info)

    await sessionmanager.close()


asyncio.run(main())
