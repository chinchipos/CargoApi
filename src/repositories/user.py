import traceback
from typing import List

from sqlalchemy import select as sa_select, delete as sa_delete, and_
from sqlalchemy.orm import joinedload, aliased

from src.database.models import User as UserOrm, AdminCompany as AdminCompanyOrm, Role as RoleOrm, Company as CompanyOrm
from src.repositories.base import BaseRepository
from src.schemas.user import UserCreateSchema
from src.utils import enums
from src.utils.exceptions import DBException


class UserRepository(BaseRepository):

    async def get_user(self, user_id: str) -> UserOrm:
        stmt = (
            sa_select(UserOrm)
            .options(
                joinedload(UserOrm.admin_company).joinedload(AdminCompanyOrm.company),
                joinedload(UserOrm.role)
            )
            .where(UserOrm.id == user_id)
            .limit(1)
        )
        dataset = await self.session.scalars(stmt)
        user = dataset.first()
        return user

    async def create_user(self, user: UserCreateSchema) -> UserOrm:
        new_user = UserOrm(**user.model_dump())
        await self.save_object(new_user)
        await self.get_user(new_user.id)
        return self.user

    async def get_companies_users(self) -> List[UserOrm]:
        roles = [enums.Role.COMPANY_ADMIN.name, enums.Role.COMPANY_LOGIST.name, enums.Role.COMPANY_DRIVER.name]
        user_table = aliased(UserOrm, name="user_tbl")
        role_table = aliased(RoleOrm, name="role_tbl")
        helper_subquery = (
            sa_select(user_table.id, CompanyOrm.name.label("company_name"))
            .select_from(user_table, role_table)
            .where(role_table.id == user_table.role_id)
            .where(role_table.name.in_(roles))
        )

        if self.user.role.name == enums.Role.CARGO_SUPER_ADMIN.name:
            helper_subquery = helper_subquery.outerjoin(CompanyOrm, CompanyOrm.id == user_table.company_id)

        elif self.user.role.name == enums.Role.CARGO_MANAGER.name:
            company_ids_stmt = (
                sa_select(AdminCompanyOrm.id)
                .where(AdminCompanyOrm.user_id == self.user.id)
            )
            company_ids = await self.select_all(company_ids_stmt, scalars=False)

            helper_subquery = helper_subquery.join(CompanyOrm, and_(
                CompanyOrm.id == user_table.company_id,
                CompanyOrm.id.in_(company_ids)
            ))

        elif self.user.role.name == enums.Role.COMPANY_ADMIN.name:
            helper_subquery = helper_subquery.join(CompanyOrm, and_(
                CompanyOrm.id == user_table.company_id,
                CompanyOrm.id == self.user.company_id
            ))

        helper_subquery = helper_subquery.subquery()
        stmt = (
            sa_select(UserOrm, helper_subquery.c.company_name)
            .options(
                joinedload(UserOrm.company),
                joinedload(UserOrm.role)
            )
            .select_from(UserOrm, helper_subquery)
            .where(UserOrm.id == helper_subquery.c.id)
            .order_by(
                helper_subquery.c.company_name,
                UserOrm.last_name,
                UserOrm.first_name
            )
        )
        self.statement(stmt)
        dataset = await self.select_all(stmt, scalars=False)
        users = [data[0] for data in dataset]
        return users

    async def get_cargo_users(self) -> List[UserOrm]:
        stmt = (
            sa_select(UserOrm)
            .options(
                joinedload(UserOrm.admin_company).joinedload(AdminCompanyOrm.company),
                joinedload(UserOrm.role)
            )
            .join(UserOrm.role)
            .filter(RoleOrm.name.in_([enums.Role.CARGO_SUPER_ADMIN.name, enums.Role.CARGO_MANAGER.name]))
            .order_by(RoleOrm.name, UserOrm.last_name, UserOrm.first_name)
        )

        users = await self.select_all(stmt)
        return users

    async def bind_managed_companies(self, user_id: str, company_ids: List[str]) -> None:
        if company_ids:
            dataset = [{"user_id": user_id, "company_id": company_id} for company_id in company_ids]
            await self.bulk_insert_or_update(AdminCompanyOrm, dataset)

    async def unbind_managed_companies(self, user_id: str, company_ids: List[str]) -> None:
        if company_ids:
            stmt = (
                sa_delete(AdminCompanyOrm)
                .where(AdminCompanyOrm.user_id == user_id)
                .where(AdminCompanyOrm.company_id.in_(company_ids))
            )
            try:
                await self.session.execute(stmt)
                await self.session.commit()

            except Exception:
                self.logger.error(traceback.format_exc())
                raise DBException()

    async def get_role(self, role_id: str) -> RoleOrm:
        try:
            stmt = sa_select(RoleOrm).where(RoleOrm.id == role_id)
            role = await self.select_first(stmt)
            return role

        except Exception:
            self.logger.error(traceback.format_exc())
            raise DBException()
