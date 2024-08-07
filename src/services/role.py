from typing import List

from src.database.model import models
from src.repositories.role import RoleRepository


class RoleService:

    def __init__(self, repository: RoleRepository) -> None:
        self.repository = repository
        self.logger = repository.logger

    async def get_roles(self) -> List[models.Role]:
        roles = await self.repository.get_roles()
        return roles

    async def get_companies_roles(self) -> List[models.Role]:
        roles = await self.repository.get_companies_roles()
        return roles

    async def get_cargo_roles(self) -> List[models.Role]:
        roles = await self.repository.get_cargo_roles()
        return roles
