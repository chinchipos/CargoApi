from typing import List

from src.database.models import CompanyOrm
from src.repositories.filter import FilterRepository


class FilterService:

    def __init__(self, repository: FilterRepository) -> None:
        self.repository = repository
        self.logger = repository.logger

    async def get_companies(self) -> List[CompanyOrm]:
        companies = await self.repository.get_companies()
        return companies
