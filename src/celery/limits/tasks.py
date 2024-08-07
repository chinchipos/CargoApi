import asyncio
from typing import List

from src.celery.exceptions import celery_logger
from src.celery.gpn.controller import GPNController
from src.celery.main import celery
from src.config import PROD_URI
from src.database.db import DatabaseSessionManager
from src.repositories.card import CardRepository
from src.repositories.system import SystemRepository
from src.utils.enums import ContractScheme


async def set_card_group_limit_fn(balance_ids: List[str]) -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        # Проверяем есть ли у этого клиента карты ГПН. Если ДА, то устанавливаем в ГПН новый лимит.
        system_repository = SystemRepository(session=session)
        gpn_system = await system_repository.get_system_by_short_name(
            system_fhort_name='ГПН',
            scheme=ContractScheme.OVERBOUGHT
        )

        card_repository = CardRepository(session=session)
        gpn_cards = await card_repository.get_cards_by_filters(balance_ids=balance_ids, system_id=gpn_system.id)

        if gpn_cards:
            gpn = GPNController(session, celery_logger)
            await gpn.set_card_group_limit(balance_ids)

    # Закрываем соединение с БД
    await sessionmanager.close()


@celery.task(name="SET_CARD_GROUP_LIMIT")
def set_card_group_limit(balance_ids: List[str]) -> None:
    asyncio.run(set_card_group_limit_fn(balance_ids))
