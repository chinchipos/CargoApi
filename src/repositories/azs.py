from typing import List, Dict, Any

from sqlalchemy import select as sa_select, and_
from sqlalchemy.orm import joinedload, contains_eager

from src.database.models import SystemOrm
from src.database.models.azs import AzsOrm, AzsOwnType, TerminalOrm
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

    async def get_terminals(self, system_id: str) -> List[TerminalOrm]:
        stmt = (
            sa_select(TerminalOrm)
            .join(AzsOrm, and_(
                AzsOrm.id == TerminalOrm.azs_id,
                AzsOrm.system_id == system_id
            ))
            .options(
                contains_eager(TerminalOrm.azs)
            )
        )
        terminals = await self.select_all(stmt)
        return terminals

    async def get_station_by_external_id(self, external_id: str) -> AzsOrm:
        stmt = sa_select(AzsOrm).where(AzsOrm.external_id == external_id)
        station = await self.select_first(stmt)
        return station
