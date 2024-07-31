from src.celery.card_manager import CardMgr
from src.celery.exceptions import celery_logger
from src.celery.overdraft import Overdraft
from src.config import PROD_URI
from src.connectors.irrelevant_balances import IrrelevantBalances
from src.database.db import DatabaseSessionManager


async def calc_overdrafts_fn() -> IrrelevantBalances:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        overdraft = Overdraft(session, celery_logger)
        irrelevant_balances = await overdraft.calculate()

    # Закрываем соединение с БД
    await sessionmanager.close()

    return irrelevant_balances


async def block_or_activate_cards_fn() -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        card_mgr = CardMgr(session=session, logger=celery_logger)
        await card_mgr.block_or_activate_cards()

    # Закрываем соединение с БД
    await sessionmanager.close()


async def send_overdrafts_report_fn() -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        overdraft = Overdraft(session, celery_logger)
        await overdraft.send_overdrafts_report()

    # Закрываем соединение с БД
    await sessionmanager.close()
