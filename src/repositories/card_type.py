from typing import List

from sqlalchemy import select as sa_select

from src.database.model.card_type import CardTypeOrm
from src.repositories.base import BaseRepository
from src.schemas.card_type import CardTypeCreateSchema


class CardTypeRepository(BaseRepository):

    async def create(self, card_type: CardTypeCreateSchema) -> CardTypeOrm:
        new_card_type = CardTypeOrm(**card_type.model_dump())
        await self.save_object(new_card_type)
        await self.session.refresh(new_card_type)

        return new_card_type

    async def get_card_types(self) -> List[CardTypeOrm]:
        stmt = sa_select(CardTypeOrm).order_by(CardTypeOrm.name)
        card_types = await self.select_all(stmt)
        return card_types
