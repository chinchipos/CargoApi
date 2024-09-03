from typing import List

from src.database.models import CompanyOrm
from src.repositories.filter import FilterRepository
from src.schemas.company import CompanyReadSchema, CompanyReadMinimumSchema
from src.utils.enums import Role


class FilterService:

    def __init__(self, repository: FilterRepository) -> None:
        self.repository = repository
        self.logger = repository.logger

    async def get_companies(self) -> List[CompanyReadMinimumSchema]:
        companies = await self.repository.get_companies()
        companies_read_schema = [CompanyReadMinimumSchema.model_validate(company) for company in companies]
        return companies_read_schema
