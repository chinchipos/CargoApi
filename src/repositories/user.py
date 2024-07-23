import traceback
from typing import List

from sqlalchemy import select as sa_select, delete as sa_delete
from sqlalchemy.orm import joinedload

from src.database import models
from src.repositories.base import BaseRepository
from src.schemas.user import UserCreateSchema
from src.utils import enums
from src.utils.exceptions import DBException


class UserRepository(BaseRepository):

    async def get_user(self, user_id: str) -> models.User:
        stmt = (
            sa_select(models.User)
            .options(
                joinedload(models.User.admin_company).joinedload(models.AdminCompany.company),
                joinedload(models.User.role)
            )
            .where(models.User.id == user_id)
            .limit(1)
        )
        dataset = await self.session.scalars(stmt)
        user = dataset.first()
        return user

    async def create_user(self, user: UserCreateSchema) -> models.User:
        new_user = models.User(**user.model_dump())
        await self.save_object(new_user)
        await self.get_user(new_user.id)
        return self.user

    async def get_companies_users(self) -> List[models.User]:
        roles = [enums.Role.COMPANY_ADMIN.name, enums.Role.COMPANY_LOGIST.name, enums.Role.COMPANY_DRIVER.name]
        stmt = (
            sa_select(models.User)
            .options(
                joinedload(models.User.company),
                joinedload(models.User.role)
            )
            .join(models.User.role)
            .outerjoin(models.User.company)
            .where(models.Role.name.in_(roles))
            .order_by(
                models.Company.name,
                models.User.last_name,
                models.User.first_name
            )
        )

        if self.user.role.name == enums.Role.CARGO_SUPER_ADMIN.name:
            pass

        elif self.user.role.name == enums.Role.CARGO_MANAGER.name:
            stmt = stmt.where(models.Company.id.in_(self.user.company_ids_subquery()))

        elif self.user.role.name == enums.Role.COMPANY_ADMIN.name:
            stmt = stmt.where(models.Company.id == self.user.id)

        users = await self.select_all(stmt)
        return users

    async def get_cargo_users(self) -> List[models.User]:
        stmt = (
            sa_select(models.User)
            .options(
                joinedload(models.User.admin_company).joinedload(models.AdminCompany.company),
                joinedload(models.User.role)
            )
            .join(models.User.role)
            .filter(models.Role.name.in_([enums.Role.CARGO_SUPER_ADMIN.name, enums.Role.CARGO_MANAGER.name]))
            .order_by(models.Role.name, models.User.last_name, models.User.first_name)
        )

        users = await self.select_all(stmt)
        return users

    async def bind_managed_companies(self, user_id: str, company_ids: List[str]) -> None:
        if company_ids:
            dataset = [{"user_id": user_id, "company_id": company_id} for company_id in company_ids]
            await self.bulk_insert_or_update(models.AdminCompany, dataset)

    async def unbind_managed_companies(self, user_id: str, company_ids: List[str]) -> None:
        if company_ids:
            stmt = (
                sa_delete(models.AdminCompany)
                .where(models.AdminCompany.user_id == user_id)
                .where(models.AdminCompany.company_id.in_(company_ids))
            )
            try:
                await self.session.execute(stmt)
                await self.session.commit()

            except Exception:
                self.logger.error(traceback.format_exc())
                raise DBException()

    async def get_role(self, role_id: str) -> models.Role:
        try:
            stmt = sa_select(models.Role).where(models.Role.id == role_id)
            role = await self.select_first(stmt)
            return role

        except Exception:
            self.logger.error(traceback.format_exc())
            raise DBException()
