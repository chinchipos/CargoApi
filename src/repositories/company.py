from typing import List, Tuple

from sqlalchemy import select as sa_select
from sqlalchemy.orm import joinedload, selectinload, aliased, load_only

from src.database.models import (Company as CompanyOrm, Balance as BalanceOrm, AdminCompany as AdminCompanyOrm,
                                 User as UserOrm, Role as RoleOrm, BalanceSystemTariff as BalanceSystemTariffOrm,
                                 System as SystemOrm)
from src.repositories.base import BaseRepository
from src.repositories.transaction import TransactionRepository
from src.utils import enums


class CompanyRepository(BaseRepository):

    async def get_company(self, company_id: str) -> CompanyOrm:
        # Получаем полные сведения об организации
        stmt = (
            sa_select(CompanyOrm)
            .options(
                (
                    selectinload(CompanyOrm.balances)
                    .selectinload(BalanceOrm.tariffs_history)
                    .joinedload(TariffHistoryOrm.system, TariffHistoryOrm.tariff)
                ),
                selectinload(CompanyOrm.users).joinedload(UserOrm.role)
            )
            .where(CompanyOrm.id == company_id)
            .join(TariffHistoryOrm, TariffHistoryOrm.balance_id == BalanceOrm.id)
            .where(TariffHistoryOrm.is_active)
        )
        dataset = await self.session.scalars(stmt)
        company = dataset.all()
        print(len(company))
        for balance in company.balances:
            for tariff_history in balance.tariffs_history:
                print('------------------------------')
                print(balance, tariff_history)
                print('System:', tariff_history.system)
                print('Tariff:', tariff_history.tariff)

        # Добавляем сведения о количестве карт
        # stmt = sa_select(sa_func.count(models.Card.id)).filter_by(company_id=company_id)
        # amount = await self.select_single_field(stmt)
        # company.annotate({'cards_amount': amount})

        return company

    async def get_company_by_balance_id(self, balance_id: str) -> CompanyOrm:
        org = aliased(CompanyOrm, name="org")
        balance = aliased(BalanceOrm, name="balance")
        stmt = (
            sa_select(org)
            .select_from(org, balance)
            .where(balance.id == balance_id)
            .where(org.id == balance.company_id)
        )
        company = await self.select_first(stmt)
        return company

    async def get_companies(self) -> List[CompanyOrm]:
        # Получаем полные сведения об организациях
        """
        stmt = (
            sa_select(CompanyOrm, sa_func.count(models.Card.id).label('cards_amount'))
            .select_from(models.Card)
            .outerjoin(CompanyOrm.cards)
            .group_by(CompanyOrm)
            .order_by(CompanyOrm.name)
            .options(
                selectinload(CompanyOrm.tariff),
                selectinload(CompanyOrm.users).joinedload(UserOrm.role)
            )
        )
        """
        stmt = (
            sa_select(CompanyOrm)
            .options(
                load_only(
                    CompanyOrm.id,
                    CompanyOrm.name,
                    CompanyOrm.inn,
                    CompanyOrm.personal_account,
                    CompanyOrm.date_add
                )
            )
            .options(
                selectinload(CompanyOrm.balances)
                .load_only(
                    BalanceOrm.id,
                    BalanceOrm.scheme,
                    BalanceOrm.balance,
                    BalanceOrm.min_balance,
                    BalanceOrm.min_balance_period,
                    BalanceOrm.min_balance_period_end_date
                )
                .selectinload(BalanceOrm.balance_system_tariff)
                .load_only()
                .joinedload(BalanceSystemTariffOrm.system)
                .load_only(SystemOrm.id, SystemOrm.full_name)
            )
            .options(
                selectinload(CompanyOrm.users)
                .load_only(
                    UserOrm.id,
                    UserOrm.username,
                    UserOrm.first_name,
                    UserOrm.last_name,
                    UserOrm.phone
                )
                .joinedload(UserOrm.role)
                .load_only(RoleOrm.id, RoleOrm.name,  RoleOrm.title,  RoleOrm.description)
            )
        )
        company_roles = [enums.Role.COMPANY_ADMIN.name, enums.Role.COMPANY_LOGIST.name, enums.Role.COMPANY_DRIVER]
        if self.user.role.name == enums.Role.CARGO_MANAGER.name:
            company_ids_subquery = self.user.company_ids_subquery()
            stmt = stmt.join(company_ids_subquery, company_ids_subquery.c.id == CompanyOrm.id)

        elif self.user.role.name in company_roles:
            stmt = stmt.where(CompanyOrm.id == self.user.company_id)

        companies = await self.select_all(stmt, scalars=True)

        def annotate_systems(company: CompanyOrm) -> CompanyOrm:
            for balance in company.balances:
                systems = [bst.system for bst in balance.balance_system_tariff]
                balance.annotate({"systems": systems})
            return company

        companies = list(map(annotate_systems, companies))
        # companies = list(map(lambda data: data[0].annotate({'cards_amount': data[1]}), dataset))
        # companies = list(map(lambda data: data[0].annotate({'cards_amount': 0}), dataset))

        return companies

    async def get_drivers(self, company_id: str = None) -> UserOrm:
        stmt = (
            sa_select(UserOrm)
            .options(
                joinedload(UserOrm.company),
                joinedload(UserOrm.role),
            )
            .join(UserOrm.company)
            .where(RoleOrm.name == enums.Role.COMPANY_DRIVER.name)
            # .where(UserOrm.role_id == RoleOrm.id)
            .order_by(CompanyOrm.name, UserOrm.last_name, UserOrm.first_name)
        )
        if company_id:
            stmt = stmt.where(UserOrm.company_id == company_id)

        drivers = await self.select_all(stmt)
        return drivers

    async def bind_manager(self, company_id: str, user_id: str) -> None:
        new_company_nanager_link = AdminCompanyOrm(company_id = company_id, user_id = user_id)
        await self.save_object(new_company_nanager_link)

    async def set_company_balance_by_last_transaction(self, balance_id: str) -> Tuple[CompanyOrm, float]:
        # Получаем организацию
        company = await self.get_company_by_balance_id(balance_id)

        # Получаем последнюю транзакцию
        transaction_repository = TransactionRepository(self.session, self.user)
        last_transaction = await transaction_repository.get_last_transaction(balance_id)

        # Устанавливаем текущий баланс организации
        await self.update_object(company, update_data={"balance": last_transaction.company_balance})
        return company, last_transaction.company_balance
