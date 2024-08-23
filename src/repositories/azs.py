from typing import List

from sqlalchemy import select as sa_select
from sqlalchemy.orm import joinedload

from src.database.models import SystemOrm
from src.database.models.azs import AzsOrm
from src.repositories.base import BaseRepository


class AzsRepository(BaseRepository):

    async def get_stations(self, system_id: str = None) -> List[AzsOrm]:
        stmt = (
            sa_select(AzsOrm)
            .options(
                joinedload(AzsOrm.system)
                .load_only(SystemOrm.id, SystemOrm.full_name)
            )
            .order_by(AzsOrm.system_id, AzsOrm.name)
        )
        if system_id:
            stmt = stmt.where(AzsOrm.system_id == system_id)
        stations = await self.select_all(stmt)
        return stations
