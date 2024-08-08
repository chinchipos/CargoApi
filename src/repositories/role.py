from typing import List

from sqlalchemy import select as sa_select

from src.database.model import models
from src.repositories.base import BaseRepository
from src.utils import enums


class RoleRepository(BaseRepository):

    async def get_roles(self, role_names: List[str] = None) -> List[models.Role]:
        stmt = sa_select(models.Role).order_by(models.Role.name)
        if role_names:
            stmt = stmt.where(models.Role.name.in_(role_names))

        roles = await self.select_all(stmt)
        return roles

    async def get_companies_roles(self) -> List[models.Role]:
        role_names = [enums.Role.COMPANY_ADMIN.name, enums.Role.COMPANY_LOGIST.name, enums.Role.COMPANY_DRIVER.name]
        roles = await self.get_roles(role_names)
        return roles

    async def get_cargo_roles(self) -> List[models.Role]:
        role_names = [enums.Role.CARGO_SUPER_ADMIN.name, enums.Role.CARGO_MANAGER.name]
        roles = await self.get_roles(role_names)
        return roles
