import asyncio
import sys

from src.connectors.exceptions import sync_task_logger
from src.celery.init import sessionmanager
from src.celery.service import clear_old_temporary_overdrafts
from src.celery.sync import run_sync


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
