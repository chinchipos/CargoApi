import asyncio
import sys

from src.celery_app.ops.controller import OpsController
from src.celery_app.main import celery
from src.config import PROD_URI
from src.database.db import DatabaseSessionManager


async def ops_import_cards_fn() -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        ops_controller = OpsController(session)
        await ops_controller.init_system()
        await ops_controller.import_cards()

    # Закрываем соединение с БД
    await sessionmanager.close()


@celery.task(name="OPS_IMPORT_CARDS")
def ops_import_cards() -> None:
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(ops_import_cards_fn())
