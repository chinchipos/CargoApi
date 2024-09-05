from typing import List

from src.database.models import AzsOrm
from src.repositories.azs import AzsRepository


class AzsService:

    def __init__(self, repository: AzsRepository) -> None:
        self.repository = repository
        self.logger = repository.logger

    async def get_filtered_stations(self, term: str) -> List[AzsOrm]:
        stations = await self.repository.get_filtered_stations(term)
        return stations
