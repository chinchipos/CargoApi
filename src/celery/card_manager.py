from typing import List, Dict, Any, Tuple

from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.connectors.khnp.connector import KHNPConnector
from src.connectors.khnp.parser import CardStatus
from src.database.model.card import CardOrm, BlockingCardReason
from src.database.model.models import (Balance as BalanceOrm,
                                       Company as CompanyOrm, System as SystemOrm)
from src.repositories.base import BaseRepository
from src.repositories.card import CardRepository
from src.utils.enums import ContractScheme
from src.utils.log import ColoredLogger

balance_id_str_type = str
card_number_str_type = str


class CardMgr(BaseRepository):

    def __init__(self, session: AsyncSession, logger: ColoredLogger):
        super().__init__(session, None)
        self.logger = logger
        self.balances_to_block_cards = []
        self.balances_to_activate_cards = []
        self.all_cards_to_block = []
        self.all_cards_to_activate = []

    async def block_or_activate_cards(self) -> None:
        """
        Этапы:
        1. Определяем какие статусы должны быть у всех существующих карт локально
        2. По каждой системе:
            2.1. Получаем статусы карт из системы
            2.2. Уточняем и устанавливаем статусы карт локально (бывают ситуации, когда статус карты локально зависит
                 от статуса в системе пшставщика и не может быть изменен, пока статус в системе не поменяется)
            2.3. Устанавливаем статусы карт в системе
        """

        # Определяем какие статусы должны быть у карт локально
        self.logger.info("Определяю какие статусы должны быть у карт локально")
        await self._calc_card_states()

        # Действия в отношении ХНП
        await self.process_khnp()

    async def _calc_card_states(self) -> None:
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
                # Делаем пометку о том, что у этого баланса карты должны находиться в заблокированном состоянии
                self.balances_to_block_cards.append(balance)

            else:
                # Делаем пометку о том, что у этого баланса карты должны находиться в разблокированном состоянии
                self.balances_to_activate_cards.append(balance)

        card_repository = CardRepository(session=self.session)

        for balance in self.balances_to_block_cards:
            self.log_decision(
                company=balance.company,
                transaction_balance=balance.balance,
                required_card_states="заблокированы"
            )
        balance_ids_to_block_cards = [balance.id for balance in self.balances_to_block_cards]
        self.all_cards_to_block = await card_repository.get_cards_by_balance_ids(balance_ids_to_block_cards)

        for balance in self.balances_to_activate_cards:
            self.log_decision(
                company=balance.company,
                transaction_balance=balance.balance,
                required_card_states="разблокированы"
            )
        balance_ids_to_activate_cards = [balance.id for balance in self.balances_to_activate_cards]
        self.all_cards_to_activate = await card_repository.get_cards_by_balance_ids(balance_ids_to_activate_cards)

    async def process_khnp(self) -> None:
        # Получаем статусы карт из системы ХНП
        khnp_connector = KHNPConnector(self.session, self.logger)
        await khnp_connector.init_system()
        khnp_cards = khnp_connector.get_khnp_cards()

        # Получаем из локальной БД карты, принадлежащие системе ХНП
        local_cards_to_be_active = self._filter_system_cards(self.all_cards_to_activate, khnp_connector.system)
        local_cards_to_be_blocked = self._filter_system_cards(self.all_cards_to_block, khnp_connector.system)

        # Сверяем статусы карт локально и в системе
        khnp_cards_to_change_state, local_cards = self._compare_card_states(
            khnp_cards=khnp_cards,
            local_cards_to_be_active=local_cards_to_be_active,
            local_cards_to_be_blocked=local_cards_to_be_blocked
        )

        # Устанавливаем статусы карт локально
        self.logger.info("Обновляю статусы карт в локальной БД")
        dataset = [
            {
                "id": card.id,
                "is_active": card.is_active,
                "reason_for_blocking": card.reason_for_blocking
            } for card in local_cards
        ]
        await self.bulk_update(CardOrm, dataset)

        # Устанавливаем статусы карт в ХНП
        self.logger.info("Обновляю статусы карт в ХНП")
        khnp_connector.change_card_states(khnp_cards_to_change_state)

    """
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
    """

    @staticmethod
    def _filter_system_cards(cards: List[CardOrm], filter_system: SystemOrm) -> List[CardOrm]:
        system_cards = []
        for card in cards:
            for system in card.systems:
                if system.id == filter_system.id:
                    system_cards.append(card)

        return system_cards

    @staticmethod
    def _compare_card_states(khnp_cards: List[Dict[str, Any]], local_cards_to_be_active: List[CardOrm],
                             local_cards_to_be_blocked: List[CardOrm]) -> Tuple[List[str], List[CardOrm]]:
        khnp_cards_to_change_state = []
        # Активные карты
        for local_card in local_cards_to_be_active:
            for khnp_card in khnp_cards:
                if khnp_card["cardNo"] == local_card.card_number:
                    # В ХНП карта заблокирована по ПИН
                    if khnp_card["status_name"] == "Заблокирована по ПИН":
                        local_card.is_active = False
                        local_card.reason_for_blocking = BlockingCardReason.PIN

                    # В ХНП карта заблокирована или помечена на блокировку
                    elif khnp_card["cardBlockRequest"] in [CardStatus.BLOCKING_PENDING.value, CardStatus.BLOCKED.value]:
                        if khnp_card["status_name"] == "Активная":
                            khnp_cards_to_change_state.append(local_card.card_number)
                            local_card.reason_for_blocking = BlockingCardReason.MANUALLY

                    break

        # Заблокированные карты: ручная блокировка
        for local_card in local_cards_to_be_blocked:
            if local_card.reason_for_blocking in [BlockingCardReason.MANUALLY, None]:
                if local_card.reason_for_blocking is None:
                    local_card.reason_for_blocking = BlockingCardReason.MANUALLY

                for khnp_card in khnp_cards:
                    if khnp_card["cardNo"] == local_card.card_number:
                        # В ХНП карта заблокирована по ПИН
                        if khnp_card["status_name"] == "Заблокирована по ПИН":
                            local_card.is_active = False
                            local_card.reason_for_blocking = BlockingCardReason.PIN

                        # В ХНП карта разблокирована или помечена на разблокировку
                        elif khnp_card["cardBlockRequest"] in [CardStatus.ACTIVE.value,
                                                               CardStatus.ACTIVATE_PENDING.value]:
                            khnp_cards_to_change_state.append(local_card.card_number)

                        break

        # Заблокированные карты: блокировка по ПИН
        for local_card in local_cards_to_be_blocked:
            if local_card.reason_for_blocking == BlockingCardReason.PIN:
                for khnp_card in khnp_cards:
                    if khnp_card["cardNo"] == local_card.card_number:
                        if khnp_card["status_name"] == "Активная":
                            if khnp_card["cardBlockRequest"] in [CardStatus.ACTIVE.value,
                                                                 CardStatus.BLOCKING_PENDING.value]:
                                local_card.is_active = True
                                local_card.reason_for_blocking = None

                            if khnp_card["cardBlockRequest"] == CardStatus.BLOCKING_PENDING.value:
                                khnp_cards_to_change_state.append(local_card.card_number)

                            if khnp_card["cardBlockRequest"] == CardStatus.BLOCKED.value:
                                local_card.is_active = False
                                local_card.reason_for_blocking = BlockingCardReason.MANUALLY

                            if khnp_card["cardBlockRequest"] == CardStatus.ACTIVATE_PENDING.value:
                                local_card.is_active = True
                                local_card.reason_for_blocking = None

                        elif khnp_card["status_name"] == "Заблокирована по ПИН":
                            if khnp_card["cardBlockRequest"] == CardStatus.ACTIVATE_PENDING.value:
                                khnp_cards_to_change_state.append(local_card.card_number)

                        break

        local_cards: List[CardOrm] = local_cards_to_be_active + local_cards_to_be_blocked
        return khnp_cards_to_change_state, local_cards

    def log_decision(self, company: CompanyOrm, transaction_balance: float, required_card_states: str) -> None:
        message = (
            f"необходимое состояние карт: {required_card_states} | "
            f"{company.name} | "
            f"услуга овердрафт: {'подключена' if company.overdraft_on else 'не подключена'} | "
            f"min_balance: {company.min_balance} | "
            f"overdraft_sum: {company.overdraft_sum} | "
            f"balance: {transaction_balance}"
        )
        self.logger.info(message)
