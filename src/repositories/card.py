import traceback
from typing import List

from sqlalchemy import select as sa_select, delete as sa_delete, func as sa_func
from sqlalchemy.orm import joinedload, selectinload, load_only, aliased

from src.database import models
from src.repositories.base import BaseRepository
from src.schemas.card import CardCreateSchema
from src.utils import enums
from src.utils.exceptions import DBException


class CardRepository(BaseRepository):

    async def create(self, create_schema: CardCreateSchema) -> models.Card:
        new_card = models.Card(**create_schema.model_dump())
        await self.save_object(new_card)
        await self.session.refresh(new_card)

        return new_card

    async def get_card(self, card_id: str) -> models.Card:
        stmt = (
            sa_select(models.Card)
            .options(
                joinedload(models.Card.card_system).joinedload(models.CardSystem.system),
                joinedload(models.Card.card_type),
                joinedload(models.Card.company),
                joinedload(models.Card.belongs_to_car),
                joinedload(models.Card.belongs_to_driver)
            )
            .where(models.Card.id == card_id)
        )

        card = await self.select_first(stmt)
        return card

    async def get_cards(self, card_numbers: List[str] = None) -> List[models.Card]:
        card = aliased(models.Card, name = "card")
        stmt = (
            sa_select(card)
            .options(
                load_only(
                    card.id,
                    card.card_number,
                    card.is_active,
                    card.date_last_use,
                    card.manual_lock
                )
            )
            .options(
                joinedload(card.card_type)
                .load_only(models.CardType.id, models.CardType.name)
            )
            .options(
                joinedload(card.company)
                .load_only(models.Company.id, models.Company.name, models.Company.inn)
            )
            .options(
                joinedload(card.belongs_to_car)
                .load_only(models.Car.id, models.Car.model, models.Car.reg_number)
            )
            .options(
                joinedload(card.belongs_to_driver)
                .load_only(models.User.id, models.User.first_name, models.User.last_name)
            )
            .options(
                selectinload(card.systems)
                .load_only(models.System.id, models.System.full_name)
            )
        )

        if card_numbers:
            stmt = stmt.where(card.card_number.in_(card_numbers))

        if self.user.role.name == enums.Role.CARGO_MANAGER.name:
            stmt = stmt.where(card.company_id.in_(self.user.company_ids_subquery()))

        elif self.user.role.name in [enums.Role.COMPANY_ADMIN.name, enums.Role.COMPANY_LOGIST.name]:
            stmt = stmt.where(card.company_id == self.user.company_id)

        elif self.user.role.name == enums.Role.COMPANY_DRIVER.name:
            stmt = (
                stmt
                .where(card.company_id == self.user.company_id)
                .where(card.belongs_to_driver_id == self.user.id)
            )

        cards = await self.select_all(stmt)
        return cards

    async def bind_managed_companies(self, card_id: str, system_ids: List[str]) -> None:
        if system_ids:
            dataset = [{"card_id": card_id, "system_id": system_id} for system_id in system_ids]
            await self.bulk_insert_or_update(models.CardSystem, dataset)

    async def unbind_managed_companies(self, card_id: str, system_ids: List[str]) -> None:
        if system_ids:
            stmt = (
                sa_delete(models.CardSystem)
                .where(models.CardSystem.card_id == card_id)
                .where(models.CardSystem.system_id.in_(system_ids))
            )
            try:
                await self.session.execute(stmt)
                await self.session.commit()

            except Exception:
                self.logger.error(traceback.format_exc())
                raise DBException()

    async def has_transactions(self, card_id: str) -> bool:
        stmt = sa_select(sa_func.count(models.Transaction.id)).where(models.Transaction.card_id == card_id)
        amount = await self.select_single_field(stmt)
        return amount > 0

    async def delete(self, card_id: str) -> None:
        try:
            # Удаляем связь Карта-Система
            stmt = sa_delete(models.CardSystem).where(models.CardSystem.card_id == card_id)
            await self.session.execute(stmt)

            # Удаляем карту
            stmt = sa_delete(models.Card).where(models.Card.id == card_id)
            await self.session.execute(stmt)

            await self.session.commit()

        except Exception:
            self.logger.error(traceback.format_exc())
            raise DBException()

    async def get_systems(self, system_ids: List[str]) -> List[models.System]:
        stmt = sa_select(models.System).where(models.System.id.in_(system_ids))
        systems = await self.select_all(stmt)
        return systems
