from datetime import date
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from src.celery_app.exceptions import CeleryError
from src.database.models import CardOrm
from src.database.models.tariff import TariffOrm
from src.database.models.balance_system_tariff import BalanceSystemTariffOrm
from src.repositories.card import CardRepository


async def get_local_cards(session: AsyncSession, system_id: str, card_numbers: List[str] | None = None) \
        -> List[CardOrm]:
    card_repository = CardRepository(session=session, user=None)
    local_cards = await card_repository.get_cards_by_filters(
        system_id=system_id,
        card_numbers=card_numbers
    )
    return local_cards


async def get_local_card(card_number, local_cards: List[CardOrm]) -> CardOrm:
    for card in local_cards:
        if card.card_number == card_number:
            return card

    raise CeleryError(trace=True, message=f'Карта с номером {card_number} не найдена в БД')


"""
def get_tariff_on_date_by_balance(balance_id: str, transaction_date: date,
                                  tariffs_history: List[BalanceTariffHistoryOrm]) -> TariffOrm | None:
    for th in tariffs_history:
        if th.balance_id == balance_id and th.start_date <= transaction_date \
                and (th.end_date is None or th.end_date > transaction_date):
            return th.tariff
"""


def get_current_tariff_by_balance(balance_id: str, bst_list: List[BalanceSystemTariffOrm]) -> TariffOrm:
    for bst in bst_list:
        if bst.balance_id == balance_id:
            return bst.tariff
