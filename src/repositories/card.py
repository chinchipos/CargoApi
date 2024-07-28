import traceback
from typing import List, Set

from sqlalchemy import select as sa_select, delete as sa_delete, func as sa_func
from sqlalchemy.orm import joinedload, selectinload, load_only, aliased

from src.database.model.card import CardOrm
from src.database.model.models import (User as UserOrm, Transaction as TransactionOrm, System as SystemOrm,
                                       Car as CarOrm, CardType as CardTypeOrm, Company as CompanyOrm,
                                       CardSystem as CardSystemOrm, Balance as BalanceOrm)
from src.repositories.base import BaseRepository
from src.schemas.card import CardCreateSchema
from src.utils import enums
from src.utils.enums import ContractScheme
from src.utils.exceptions import DBException


class CardRepository(BaseRepository):

    async def create(self, create_schema: CardCreateSchema) -> CardOrm:
        new_card = CardOrm(**create_schema.model_dump())
        await self.save_object(new_card)
        await self.session.refresh(new_card)

        return new_card

    async def get_card(self, card_id: str) -> CardOrm:
        stmt = (
            sa_select(CardOrm)
            .options(
                load_only(
                    CardOrm.id,
                    CardOrm.card_number,
                    CardOrm.is_active,
                    CardOrm.reason_for_blocking,
                    CardOrm.date_last_use,
                    CardOrm.company_id
                )
            )
            .options(
                selectinload(CardOrm.systems)
                .load_only(SystemOrm.id, SystemOrm.full_name)
            )
            .options(
                joinedload(CardOrm.card_type)
                .load_only(CardTypeOrm.id, CardTypeOrm.name)
            )
            .options(
                joinedload(CardOrm.company)
                .load_only(CompanyOrm.id, CompanyOrm.name, CompanyOrm.inn)
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
                load_only(
                    CardOrm.id,
                    CardOrm.card_number,
                    CardOrm.is_active,
                    CardOrm.reason_for_blocking,
                    CardOrm.date_last_use
                )
            )
            .options(
                selectinload(CardOrm.systems)
                .load_only(SystemOrm.id, SystemOrm.full_name)
            )
            .options(
                joinedload(CardOrm.card_type)
                .load_only(CardTypeOrm.id, CardTypeOrm.name)
            )
            .options(
                joinedload(CardOrm.company)
                .load_only(CompanyOrm.id, CompanyOrm.name, CompanyOrm.inn)
            )
            .options(
                joinedload(CardOrm.belongs_to_car)
                .load_only(CarOrm.id, CarOrm.model, CarOrm.reg_number)
            )
            .options(
                joinedload(CardOrm.belongs_to_driver)
                .load_only(UserOrm.id, UserOrm.first_name, UserOrm.last_name)
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

    async def get_cards_by_balance_ids(self, balance_ids: List[str] | Set[str]) -> List[CardOrm]:
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
