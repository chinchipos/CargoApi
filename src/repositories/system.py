from typing import List

from sqlalchemy import select as sa_select, func as sa_func, null
from sqlalchemy.orm import aliased, selectinload

from src.database import models
from src.repositories.base import BaseRepository


class SystemRepository(BaseRepository):

    async def get_system(self, system_id: str) -> models.System:
        system = await self.session.get(models.System, system_id)
        return system

    """
    async def create(self, create_schema: SystemCreateSchema) -> models.System:
        new_system = models.System(**create_schema.model_dump())
        await self.save_object(new_system)
        new_system = await self.get_system(new_system.id)
        return new_system
    """

    async def get_systems(self) -> List[models.System]:
        subq_cards_total = (
            sa_select(
                models.System.id,
                sa_func.count(models.CardBinding.id).label('cards_amount_total'),
            )
            .select_from(models.CardBinding)
            .group_by(models.System.id)
            .subquery("helper_cards_total")
        )

        subq_cards_in_use = (
            sa_select(
                models.System.id,
                sa_func.count(models.CardBinding.id).label('cards_amount_in_use'),
            )
            .select_from(models.CardBinding)
            .where(models.CardBinding.balance_id.is_not(null()))
            .group_by(models.System.id)
            .subquery("helper_cards_in_use")
        )

        stmt = (
            sa_select(
                models.System,
                subq_cards_total.c.cards_amount_total,
                subq_cards_in_use.c.cards_amount_in_use
            )
            .join(subq_cards_total, subq_cards_total.c.id == models.System.id)
            .join(subq_cards_in_use, subq_cards_in_use.c.id == models.System.id)
            .options(
                selectinload(models.System.cards)
            )
        )

        dataset = await self.select_all(stmt, scalars=False)

        def annotate_amounts(data):
            data[0].annotate({'cards_amount_total': data[1]})
            data[0].annotate({'cards_amount_in_use': data[2]})
            data[0].annotate({'cards_amount_free': data[1] - data[2]})
            return data[0]

        systems = list(map(annotate_amounts, dataset))
        return systems

    async def get_cards_amount(self, system_id: str) -> int:
        stmt = (
            sa_select(sa_func.count(models.CardSystem.id))
            .select_from(models.CardSystem)
            .where(models.CardSystem.system_id == system_id)
        )
        amount = await self.select_single_field(stmt)
        return amount

    async def get_system_by_short_name(self, system_fhort_name: str) -> models.System:
        stmt = sa_select(models.System).where(models.System.short_name == system_fhort_name)
        system = await self.select_first(stmt)
        return system
