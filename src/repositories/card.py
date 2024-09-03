import traceback
from datetime import datetime
from typing import List

from sqlalchemy import select as sa_select, delete as sa_delete, func as sa_func, or_, null, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload, aliased

from src.config import TZ
from src.database.models import CardLimitOrm, InnerGoodsGroupOrm
from src.database.models.card import CardOrm, CardHistoryOrm
from src.database.models.card_type import CardTypeOrm
from src.database.models.user import UserOrm
from src.database.models.transaction import TransactionOrm
from src.database.models.system import SystemOrm, CardSystemOrm
from src.database.models.car import CarOrm
from src.database.models.balance import BalanceOrm
from src.database.models.company import CompanyOrm
from src.repositories.base import BaseRepository
from src.schemas.card import CardCreateSchema
from src.utils import enums
from src.utils.exceptions import DBException


class CardRepository(BaseRepository):

    def __init__(self, session: AsyncSession, user: UserOrm | None = None):
        super().__init__(session, user)
        self.card_groups = []

    async def create(self, create_schema: CardCreateSchema) -> CardOrm:
        new_card = CardOrm(**create_schema.model_dump())
        await self.save_object(new_card)
        await self.session.refresh(new_card)

        return new_card

    async def get_card(self, card_id: str) -> CardOrm:
        stmt = (
            sa_select(CardOrm)
            .options(
                selectinload(CardOrm.systems)
            )
            .options(
                joinedload(CardOrm.card_type)
                .load_only(CardTypeOrm.id, CardTypeOrm.name)
            )
            .options(
                joinedload(CardOrm.company)
            )
            .options(
                joinedload(CardOrm.belongs_to_car)
                .load_only(CarOrm.id, CarOrm.model, CarOrm.reg_number)
            )
            .options(
                joinedload(CardOrm.belongs_to_driver)
                .load_only(UserOrm.id, UserOrm.first_name, UserOrm.last_name)
            )
            .where(CardOrm.id == card_id)
        )

        card = await self.select_first(stmt)
        return card

    async def get_cards(self, card_numbers: List[str] = None) -> List[CardOrm]:
        company_table = aliased(CompanyOrm, name="org")
        stmt = (
            sa_select(CardOrm)
            .options(
                selectinload(CardOrm.systems)
                .load_only(SystemOrm.id, SystemOrm.full_name, SystemOrm.short_name, SystemOrm.limits_on)
            )
            .options(
                joinedload(CardOrm.card_type)
                .load_only(CardTypeOrm.id, CardTypeOrm.name)
            )
            .options(
                joinedload(CardOrm.company)
                .load_only(CompanyOrm.id, CompanyOrm.name, CompanyOrm.inn, CompanyOrm.personal_account)
            )
            .options(
                joinedload(CardOrm.belongs_to_car)
                .load_only(CarOrm.id, CarOrm.model, CarOrm.reg_number)
            )
            .options(
                joinedload(CardOrm.belongs_to_driver)
                .load_only(UserOrm.id, UserOrm.first_name, UserOrm.last_name)
            )
            .options(
                selectinload(CardOrm.limits)
                .load_only(CardLimitOrm.id)
            )
            .outerjoin(company_table, company_table.id == CardOrm.company_id)
            .order_by(company_table.name, CardOrm.card_number)
        )

        if card_numbers:
            stmt = stmt.where(CardOrm.card_number.in_(card_numbers))

        if self.user.role.name == enums.Role.CARGO_MANAGER.name:
            company_ids_subquery = self.user.company_ids_subquery()
            stmt = stmt.join(company_ids_subquery, company_ids_subquery.c.id == CardOrm.company_id)
            # stmt = stmt.where(card.company_id.in_(self.user.company_ids_subquery()))

        elif self.user.role.name in [enums.Role.COMPANY_ADMIN.name, enums.Role.COMPANY_LOGIST.name]:
            stmt = stmt.where(CardOrm.company_id == self.user.company_id)

        elif self.user.role.name == enums.Role.COMPANY_DRIVER.name:
            stmt = (
                stmt
                .where(CardOrm.company_id == self.user.company_id)
                .where(CardOrm.belongs_to_driver_id == self.user.id)
            )
        # self.statement(stmt)
        cards = await self.select_all(stmt)
        for card in cards:
            card.annotate({"limits_count": len(card.limits)})

        return cards

    async def bind_systems(self, card_id: str, system_ids: List[str]) -> None:
        if system_ids:
            dataset = [{"card_id": card_id, "system_id": system_id} for system_id in system_ids]
            await self.bulk_insert_or_update(CardSystemOrm, dataset)

    async def unbind_systems(self, card_id: str, system_ids: List[str]) -> None:
        if system_ids:
            stmt = (
                sa_delete(CardSystemOrm)
                .where(CardSystemOrm.card_id == card_id)
                .where(CardSystemOrm.system_id.in_(system_ids))
            )
            try:
                await self.session.execute(stmt)
                await self.session.commit()

            except Exception:
                self.logger.error(traceback.format_exc())
                raise DBException()

    async def bulk_unbind_systems(self, card_numbers: List[str]) -> None:
        """
        Открепление карты от всех систем.
        """
        if card_numbers:
            cards = await self.get_cards(card_numbers=card_numbers)
            card_ids = [card.id for card in cards]
            stmt = (
                sa_delete(CardSystemOrm)
                .where(CardSystemOrm.card_id.in_(card_ids))
            )
            try:
                await self.session.execute(stmt)
                await self.session.commit()

                # Отвязываем от карт автомобиль, водителя, организацию. Блокируем карту.
                dataset = [
                    {
                        "id": card.id,
                        "company_id": None,
                        "belongs_to_car_id": None,
                        "belongs_to_driver_id": None,
                        "is_active": False,
                    } for card in cards
                ]
                await self.bulk_update(CardOrm, dataset)

            except Exception:
                self.logger.error(traceback.format_exc())
                raise DBException()

    async def has_transactions(self, card_id: str) -> bool:
        stmt = sa_select(sa_func.count(TransactionOrm.id)).where(TransactionOrm.card_id == card_id)
        amount = await self.select_single_field(stmt)
        return amount > 0

    async def delete(self, card_id: str) -> None:
        try:
            # Удаляем связь Карта-Система
            stmt = sa_delete(CardSystemOrm).where(CardSystemOrm.card_id == card_id)
            await self.session.execute(stmt)

            # Удаляем карту
            stmt = sa_delete(CardOrm).where(CardOrm.id == card_id)
            await self.session.execute(stmt)

            await self.session.commit()

        except Exception:
            self.logger.error(traceback.format_exc())
            raise DBException()

    async def get_systems(self, system_ids: List[str]) -> List[SystemOrm]:
        stmt = sa_select(SystemOrm).where(SystemOrm.id.in_(system_ids))
        systems = await self.select_all(stmt)
        return systems

    """
    async def get_cards_by_balance_ids(self, balance_ids: List[str]) -> List[CardOrm]:
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
            .order_by(CardOrm.card_number)
        )

        cards = await self.select_all(stmt)
        return cards
    """
    """
    async def get_cards_by_numbers(self, card_numbers: List[str] | None = None, system_id: str | None = None) \
            -> List[CardOrm]:
        stmt = (
            sa_select(CardOrm)
            .select_from(CardOrm, CardSystemOrm)
            .where(CardSystemOrm.card_id == CardOrm.id)
            .order_by(CardOrm.card_number)
        )

        if card_numbers:
            stmt = stmt.where(CardOrm.card_number.in_(card_numbers))

        if system_id:
            stmt = stmt.where(CardSystemOrm.system_id == system_id)

        cards = await self.select_all(stmt)

        return cards
    """
    """
    async def get_cards_by_system_id(self, system_id: str | None = None) -> List[CardOrm]:
        stmt = (
            sa_select(CardOrm)
            .options(
                selectinload(CardOrm.systems)
                .load_only(SystemOrm.id, SystemOrm.full_name, SystemOrm.short_name)
            )
            .options(
                joinedload(CardOrm.card_type)
                .load_only(CardTypeOrm.id, CardTypeOrm.name)
            )
            .options(
                joinedload(CardOrm.company)
                .load_only(CompanyOrm.id, CompanyOrm.name, CompanyOrm.inn, CompanyOrm.personal_account)
            )
            .order_by(CardOrm.card_number)
        )
        if system_id:
            stmt = stmt.where(CardSystemOrm.system_id == system_id).where(CardSystemOrm.card_id == CardOrm.id)
        cards = await self.select_all(stmt)
        return cards
    """

    async def get_cards_by_filters(self, balance_ids: List[str] | None = None, system_id: str | None = None,
                                   card_numbers: List[str] | None = None) -> List[CardOrm]:

        stmt = (
            sa_select(CardOrm)
            .options(
                selectinload(CardOrm.systems)
            )
            .options(
                joinedload(CardOrm.card_type)
            )
            .options(
                joinedload(CardOrm.company)
                .selectinload(CompanyOrm.balances)
            )
            .order_by(CardOrm.card_number)
        )

        if balance_ids:
            balance_table = aliased(BalanceOrm, name="balance_tbl")
            company_table = aliased(CompanyOrm, name="company_tbl")
            stmt = (
                stmt
                .where(balance_table.id.in_(balance_ids))
                .where(company_table.id == balance_table.company_id)
                .where(CardOrm.company_id == company_table.id)
            )

        if system_id:
            card_system_table = aliased(CardSystemOrm, name="cs_tbl")
            stmt = (
                stmt
                .where(card_system_table.system_id == system_id)
                .where(card_system_table.card_id == CardOrm.id)
            )

        if card_numbers:
            stmt = stmt.where(CardOrm.card_number.in_(card_numbers))

        cards = await self.select_all(stmt)
        return cards

    """
    @staticmethod
    def filter_cards_by_system(any_cards: List[CardOrm], system: SystemOrm) -> List[CardOrm]:
        system_cards = []
        for card in any_cards:
            for s in card.systems:
                if s.id == system.id:
                    system_cards.append(card)

        return system_cards
    """

    async def get_limits(self, card_id: str | None = None) -> List[CardLimitOrm]:
        stmt = (
            sa_select(CardLimitOrm)
            .options(
                joinedload(CardLimitOrm.inner_goods_group)
                .selectinload(InnerGoodsGroupOrm.outer_goods_groups)
            )
        )
        if card_id:
            stmt = stmt.where(CardLimitOrm.card_id == card_id)
        limits = await self.select_all(stmt)
        return limits

    async def delete_card_limits(self, card_id: str) -> None:
        stmt = (
            sa_delete(CardLimitOrm)
            .where(CardLimitOrm.card_id == card_id)
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def get_card_history(self) -> List[CardHistoryOrm]:
        stmt = (
            sa_select(CardHistoryOrm)
            .options(
                joinedload(CardHistoryOrm.company)
                .selectinload(CompanyOrm.balances)
            )
            .options(
                joinedload(CardHistoryOrm.card)
                .load_only(CardOrm.id, CardOrm.company_id, CardOrm.card_number)
            )
            .where(or_(
                CardHistoryOrm.end_time.is_(null()),
                and_(
                    CardHistoryOrm.begin_time <= datetime.now(tz=TZ),
                    CardHistoryOrm.end_time > datetime.now(tz=TZ)
                )
            ))
            .order_by(CardHistoryOrm.card_id)
        )
        card_history = await self.select_all(stmt)
        return card_history
