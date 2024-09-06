import copy
import json
from typing import List, Dict, Any

from sqlalchemy import select as sa_select, and_, or_, cast, String
from sqlalchemy.orm import joinedload, contains_eager

from src.database.models import SystemOrm
from src.database.models.azs import AzsOrm, AzsOwnType, TerminalOrm
from src.repositories.base import BaseRepository
from src.utils.enums import System


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

    @staticmethod
    def pretty_address(addr_json: Dict[str, Any] | str | None, system_short_name: str | None) -> str | None:
        if not addr_json:
            return None

        addr_json_ = copy.deepcopy(addr_json)
        if isinstance(addr_json_, str):
            try:
                addr_json_ = json.loads(addr_json_)
            except Exception:
                return addr_json

        if system_short_name == System.GPN.value:
            address_params = []
            if addr_json_.get("city", None):
                address_params.append(addr_json_["city"])

            if addr_json_.get("street", None):
                address_params.append(addr_json_["street"])

            if addr_json_.get("house", None):
                address_params.append(addr_json_["house"])

            if addr_json_.get("building", None):
                address_params.append(addr_json_["building"])

            if addr_json_.get("kmRoad", None):
                address_params.append(f'{addr_json_["kmRoad"]}км')

            address = ", ".join(address_params)
            return address

    async def get_filtered_stations(self, term: str) -> List[AzsOrm]:
        term = term.replace(",", ".")
        stmt = (
            sa_select(AzsOrm)
            .options(
                joinedload(AzsOrm.system)
            )
            .outerjoin(TerminalOrm, TerminalOrm.azs_id == AzsOrm.id)
            .order_by(AzsOrm.name)
        )
        if len(term) < 3:
            stmt = stmt.where(
                or_(
                    AzsOrm.external_id == term,
                    AzsOrm.name == term
                )
            )
        elif "." in term:
            stmt = stmt.where(
                or_(
                    AzsOrm.external_id.icontains(term),
                    AzsOrm.name.icontains(term),
                    cast(AzsOrm.latitude, String).icontains(term),
                    cast(AzsOrm.longitude, String).icontains(term),
                    TerminalOrm.external_id.icontains(term),
                    TerminalOrm.name.icontains(term)
                )
            )
        else:
            stmt = stmt.where(
                or_(
                    AzsOrm.external_id.icontains(term),
                    AzsOrm.name.icontains(term),
                    TerminalOrm.external_id.icontains(term),
                    TerminalOrm.name.icontains(term)
                )
            )

        # self.statement(stmt)
        stations = await self.select_all(stmt)
        for station in stations:
            pretty_address = self.pretty_address(
                addr_json=station.address,
                system_short_name=station.system.short_name if station.system else None
            )
            station.annotate({"pretty_address": pretty_address})

        return stations

    async def get_station(self, azs_id: str) -> AzsOrm:
        stmt = (
            sa_select(AzsOrm)
            .options(
                joinedload(AzsOrm.system)
            )
            .where(AzsOrm.id == azs_id)
        )
        station = await self.select_first(stmt)
        pretty_address = self.pretty_address(
            addr_json=station.address,
            system_short_name=station.system.short_name if station.system else None
        )
        station.annotate({"pretty_address": pretty_address})
        return station
