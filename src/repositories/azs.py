from typing import List, Dict, Any

from sqlalchemy import select as sa_select
from sqlalchemy.orm import joinedload

from src.database.models import SystemOrm
from src.database.models.azs import AzsOrm, AzsOwnType
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

    @staticmethod
    async def get_azs_own_types_dictionary() -> List[Dict[str, Any]]:
        azs_types = [
            {
                "id": azs_own_type.name,
                "name": azs_own_type.value,
            } for azs_own_type in AzsOwnType
        ]

        return azs_types
