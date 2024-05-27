import asyncio
import sys

from src.database.db import DatabaseSessionManager
from src.main import PROD_URI
from src.tasks.service import clear_old_temporary_overdrafts
from src.tasks.sync import run_sync

sessionmanager = DatabaseSessionManager()
sessionmanager.init(PROD_URI)


async def main():

    async with sessionmanager.session() as session:
        # Сервисные операции с БД
        await clear_old_temporary_overdrafts(session)

        # Запускаем процедуры синхронизации данных с поставщиками услуг
        await run_sync(session)

    # Закрываем соединение с БД
    await sessionmanager.close()

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

asyncio.run(main())
