from typing import List

from sqlalchemy import select as sa_select, func as sa_func

from src.database import models
from src.repositories.base import BaseRepository
from src.schemas.system import SystemCreateSchema


class SystemRepository(BaseRepository):

    async def get_system(self, system_id: str) -> models.System:
        system = await self.session.get(models.System, system_id)
        return system

    async def create(self, system: SystemCreateSchema) -> models.System:
        new_system = models.System(**system.model_dump())
        self.session.add(new_system)
        await self.session.flush()
        await self.session.commit()
        new_system = await self.get_system(new_system.id)
        return new_system

    async def get_systems(self) -> List[models.System]:
        stmt = (
            sa_select(models.System, sa_func.count(models.CardSystem.id).label('cards_amount'))
            .select_from(models.CardSystem)
            .outerjoin(models.System.card_system)
            .group_by(models.System)
            .order_by(models.System.full_name)
        )
        dataset = await self.select_all(stmt, scalars=False)
        systems = list(map(lambda data: data[0].annotate({'cards_amount': data[1]}), dataset))
        return systems

    async def get_cards_amount(self, system_id: str) -> int:
        stmt = (
            sa_select(sa_func.count(models.CardSystem.id))
            .select_from(models.CardSystem)
            .where(models.CardSystem.system_id == system_id)
        )
        amount = await self.select_single_field(stmt)
        return amount
