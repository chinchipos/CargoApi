from typing import List

from sqlalchemy import select as sa_select, func as sa_func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from src.database import models
from src.repositories.base import BaseRepository
from src.schemas.card import CardCreateSchema
from src.utils import enums
from src.utils.exceptions import DBDuplicateException


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

    async def get_cards(self) -> List[models.Card]:
        stmt = (
            sa_select(models.Card)
            .options(
                joinedload(models.Card.card_system).joinedload(models.CardSystem.system),
                joinedload(models.Card.card_type),
                joinedload(models.Card.company),
                joinedload(models.Card.belongs_to_car),
                joinedload(models.Card.belongs_to_driver)
            )
        )

        if self.user.role.name == enums.Role.CARGO_MANAGER.name:
            stmt = stmt.where(models.Card.company_id.in_(self.user.company_ids_subquery()))

        elif self.user.role.name in [enums.Role.COMPANY_ADMIN.name, enums.Role.COMPANY_LOGIST.name]:
            stmt = stmt.where(models.Card.company_id == self.user.company_id)

        elif self.user.role.name == enums.Role.COMPANY_DRIVER.name:
            stmt = (
                stmt
                .where(models.Card.company_id == self.user.company_id)
                .where(models.Card.belongs_to_driver_id == self.user.id)
            )

        cards = await self.select_all(stmt)
        return cards
