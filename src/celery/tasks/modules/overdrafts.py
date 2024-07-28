from src.celery.card_manager import CardMgr
from src.celery.exceptions import celery_logger
from src.celery.overdraft import Overdraft
from src.config import PROD_URI
from src.database.db import DatabaseSessionManager


async def calc_overdrafts_fn() -> bool:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        overdraft = Overdraft(session, celery_logger)
        await overdraft.calculate()

    # Закрываем соединение с БД
    await sessionmanager.close()

    return True


async def block_or_activate_cards_fn() -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        card_mgr = CardMgr(session=session, logger=celery_logger)
        await card_mgr.block_or_activate_cards()

    # Закрываем соединение с БД
    await sessionmanager.close()
