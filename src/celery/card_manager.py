from typing import List

from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, aliased, joinedload

from src.connectors.khnp.connector import KHNPConnector
from src.database.models import (User as UserOrm, Balance as BalanceOrm,
                                 Company as CompanyOrm, Card as CardOrm,
                                 System as SystemOrm, CardSystem as CardSystemOrm)
from src.repositories.base import BaseRepository
from src.utils.enums import ContractScheme
from src.utils.log import ColoredLogger

balance_id_str_type = str
card_number_str_type = str


class CardMgr(BaseRepository):

    def __init__(self, session: AsyncSession, user: UserOrm | None = None):
        super().__init__(session, user)
        self.logger = ColoredLogger(logfile_name='schedule.log', logger_name='CARDS')
        self.balances_to_block_cards = []
        self.balances_to_activate_cards = []

    async def block_or_activate_cards(self) -> None:
        # Получаем все перекупные балансы
        stmt = (
            sa_select(BalanceOrm)
            .options(
                joinedload(BalanceOrm.company)
            )
            .where(BalanceOrm.scheme == ContractScheme.OVERBOUGHT)
        )
        balances = await self.select_all(stmt)

        # Анализируем настройки организации и текущий баланс, делаем заключение о том,
        # какое состояние карт у этой организации должно быть
        for balance in balances:
            # Получаем размер овердрафта
            overdraft_sum = balance.company.overdraft_sum if balance.company.overdraft_on else 0
            if overdraft_sum > 0:
                overdraft_sum = -overdraft_sum

            # Получаем порог баланса, ниже которого требуется блокировка карт
            boundary = balance.company.min_balance + overdraft_sum

            if balance.balance < boundary:
                # Помечаем баланс на блокировку карт, если это требуется
                self.balances_to_block_cards.append(balance)

            else:
                # Помечаем баланс на разблокировку карт, если это требуется
                self.balances_to_activate_cards.append(balance)

        for balance in self.balances_to_block_cards:
            self.logger.info(f"Помечено на блокировку карт: {balance.company.name}")

        for balance in self.balances_to_activate_cards:
            self.logger.info(f"Помечено на разблокировку карт: {balance.company.name}")

        balance_ids_to_block_cards = [balance.id for balance in self.balances_to_block_cards]
        all_systems_cards_to_block = await self._get_cards_from_db(balance_ids_to_block_cards)

        balance_ids_to_activate_cards = [balance.id for balance in self.balances_to_activate_cards]
        all_systems_cards_to_activate = await self._get_cards_from_db(balance_ids_to_activate_cards)

        await self._block_or_activate_khnp_cards(all_systems_cards_to_block, all_systems_cards_to_activate)

    async def _get_cards_from_db(self, balance_ids: List[balance_id_str_type]) -> List[CardOrm]:
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

    async def _block_or_activate_khnp_cards(self, all_systems_cards_to_block: List[CardOrm],
                                            all_systems_cards_to_activate: List[CardOrm]) -> None:
        khnp = KHNPConnector(self.session)
        await khnp.init_system()

        # Получаем карты, принадлежащие системе ХНП
        khnp_card_numbers_to_block = self._get_khnp_card_numbers(all_systems_cards_to_block, khnp.system)
        khnp_card_numbers_to_activate = self._get_khnp_card_numbers(all_systems_cards_to_activate, khnp.system)
        await khnp.block_or_activate_cards(
            khnp_card_numbers_to_block=khnp_card_numbers_to_block,
            khnp_card_numbers_to_activate=khnp_card_numbers_to_activate,
            need_authorization=True
        )

    @staticmethod
    def _get_khnp_card_numbers(marked_systems_cards: List[CardOrm], khnp_system: SystemOrm) -> List[str]:
        khnp_card_numbers = set()
        for card in marked_systems_cards:
            for system in card.systems:
                if system.id == khnp_system.id:
                    khnp_card_numbers.add(card.card_number)

        return list(khnp_card_numbers)
