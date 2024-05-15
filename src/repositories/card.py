from typing import List

from sqlalchemy import select as sa_select, func as sa_func
from sqlalchemy.exc import IntegrityError

from src.database import models
from src.repositories.base import BaseRepository
from src.schemas.card import CardCreateSchema
from src.utils.exceptions import DBDuplicateException


class CardRepository(BaseRepository):

    async def create(self, card: CardCreateSchema) -> models.Card:
        try:
            new_card = models.Card(**card.model_dump())
            self.session.add(new_card)
            await self.session.flush()
            await self.session.commit()
            await self.session.refresh(new_card)

        except IntegrityError:
            raise DBDuplicateException()

        return new_card

    async def get_cards(self) -> List[models.Card]:
        stmt = (
            sa_select(models.Card, sa_func.count(models.Company.id).label('companies_amount'))
            .select_from(models.Company)
            .outerjoin(models.Card.companies)
            .group_by(models.Card)
            .order_by(models.Card.name)
        )
        dataset = await self.select_all(stmt, scalars=False)
        cards = list(map(lambda data: data[0].annotate({'companies_amount': data[1]}), dataset))
        return cards

    async def get_companies_amount(self, card_id: str) -> int:
        stmt = (
            sa_select(sa_func.count(models.Company.id))
            .where(models.Company.card_id == card_id)
        )
        amount = await self.select_single_field(stmt)
        return amount
