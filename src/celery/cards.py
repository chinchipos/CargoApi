from datetime import datetime, timedelta
from time import sleep
from typing import List, Tuple

from sqlalchemy import select as sa_select, null
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload, aliased

from src.config import OVERDRAFT_FEE_PERCENT, TZ
from src.connectors.khnp.connector import KHNPConnector
from src.database.models import (User as UserOrm, Transaction as TransactionOrm, Balance as BalanceOrm,
                                 OverdraftsHistory as OverdraftsHistoryOrm, Company as CompanyOrm, Card as CardOrm,
                                 System as SystemOrm, BalanceSystemTariff as BalanceSystemTariffOrm,
                                 CardSystem as CardSystemOrm)
from src.repositories.base import BaseRepository
from src.utils.enums import TransactionType, ContractScheme
from src.utils.log import ColoredLogger

balance_id_str_type = str
card_number_str_type = str


class Cards(BaseRepository):

    def __init__(self, session: AsyncSession, user: UserOrm | None = None):
        super().__init__(session, user)
        self.logger = ColoredLogger(logfile_name='schedule.log', logger_name='CARDS')

    async def block_cards(self, balance_ids: List[balance_id_str_type]) -> None:
        # Получаем список карт
        cards = await self.get_cards(balance_ids)

        # Блокируем карты в ХНП
        await self.block_cards_khnp(cards)

    async def get_cards(self, balance_ids: List[balance_id_str_type]) -> List[CardOrm]:
        card_system_table = aliased(CardSystemOrm, name="cs_tbl")
        system_table = aliased(SystemOrm, name="system_tbl")
        stmt = (
            sa_select(CardOrm)
            .options(
                selectinload(CardOrm.systems)
            )
            .select_from(CardOrm, CompanyOrm, BalanceOrm, card_system_table, system_table)
            .where(CompanyOrm.id == CardOrm.company_id)
            .where(BalanceOrm.company_id == CompanyOrm.id)
            .where(BalanceOrm.id.in_(balance_ids))
            .where(card_system_table.card_id == CardOrm.id)
            .where(system_table.id == card_system_table.system_id)
            .where(system_table.scheme == ContractScheme.OVERBOUGHT)
        )
        cards = await self.select_all(stmt)
        return cards

    async def block_cards_khnp(self, cards: List[CardOrm]) -> None:
        khnp = KHNPConnector(self.session)
        await khnp.init_system()
        await khnp.block_cards(cards)
