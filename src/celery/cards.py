from datetime import datetime, timedelta
from time import sleep
from typing import List, Tuple

from sqlalchemy import select as sa_select, null
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.config import OVERDRAFT_FEE_PERCENT, TZ
from src.database.models import (User as UserOrm, Transaction as TransactionOrm, Balance as BalanceOrm,
                                 OverdraftsHistory as OverdraftsHistoryOrm, Company as CompanyOrm, Card as CardOrm)
from src.repositories.base import BaseRepository
from src.utils.enums import TransactionType
from src.utils.log import ColoredLogger

balance_id_str_type = str
card_number_str_type = str


class Cards(BaseRepository):

    def __init__(self, session: AsyncSession, user: UserOrm | None = None):
        super().__init__(session, user)
        self.logger = ColoredLogger(logfile_name='schedule.log', logger_name='CARDS')

    async def block_cards(self, balance_ids: List[balance_id_str_type]) -> None:
        # Получаем список номеров карт
        card_numbers = await self.get_card_numbers(balance_ids)

    async def get_card_numbers(self, balance_ids: List[balance_id_str_type]) -> List[card_number_str_type]:
        stmt = (
            sa_select(CardOrm.card_number)
            .select_from(CardOrm, BalanceOrm)
            .where()
        )