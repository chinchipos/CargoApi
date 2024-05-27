import asyncio
import sys

from src.connectors.exceptions import sync_task_logger
from src.tasks.init import sessionmanager
from src.tasks.service import clear_old_temporary_overdrafts
from src.tasks.sync import run_sync
from src.utils.log import ColoredLogger


async def main():

    async with sessionmanager.session() as session:
        # Сервисные операции с БД
        sync_task_logger.info('Запускаю процедуру удаления старых овердрафтов')
        await clear_old_temporary_overdrafts(session)
        sync_task_logger.info('Завершена процедура удаления старых овердрафтов')

        # Запускаем процедуры синхронизации данных с поставщиками услуг
        sync_task_logger.info('Запускаю процедуру синхронизации данных с поставщиками услуг')
        await run_sync(session)
        sync_task_logger.info('Завершена процедура синхронизации данных с поставщиками услуг')

    # Закрываем соединение с БД
    sync_task_logger.info('Закрываю соединение с БД')
    await sessionmanager.close()

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

asyncio.run(main())
