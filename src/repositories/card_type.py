from typing import List

from sqlalchemy import select as sa_select

from src.database.model import models
from src.repositories.base import BaseRepository
from src.schemas.card_type import CardTypeCreateSchema


class CardTypeRepository(BaseRepository):

    async def create(self, card_type: CardTypeCreateSchema) -> models.CardType:
        new_card_type = models.CardType(**card_type.model_dump())
        await self.save_object(new_card_type)
        await self.session.refresh(new_card_type)

        return new_card_type

    async def get_card_types(self) -> List[models.CardType]:
        stmt = sa_select(models.CardType).order_by(models.CardType.name)
        card_types = await self.select_all(stmt)
        return card_types
