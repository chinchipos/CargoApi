from typing import List, Tuple

from sqlalchemy import select as sa_select, func as sa_func
from sqlalchemy.orm import joinedload, selectinload, raiseload, lazyload, subqueryload, aliased

from src.database import models
from src.repositories.base import BaseRepository
from src.repositories.transaction import TransactionRepository
from src.utils import enums


class CompanyRepository(BaseRepository):

    async def get_company(self, company_id: str) -> models.Company:
        # Получаем полные сведения об организации
        stmt = (
            sa_select(models.Company)
            .options(
                (
                    selectinload(models.Company.balances)
                    .selectinload(models.Balance.tariffs_history)
                    .joinedload(models.TariffHistory.system, models.TariffHistory.tariff)
                ),
                selectinload(models.Company.users).joinedload(models.User.role)
            )
            .where(models.Company.id == company_id)
            .join(models.TariffHistory, models.TariffHistory.balance_id == models.Balance.id)
            .where(models.TariffHistory.is_active)
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

    async def get_company_by_balance_id(self, balance_id: str) -> models.Company:
        org = aliased(models.Company, name="org")
        balance = aliased(models.Balance, name="balance")
        stmt = (
            sa_select(org)
            .select_from(org, balance)
            .where(balance.id == balance_id)
            .where(org.id == balance.company_id)
        )
        company = await self.select_first(stmt)
        return company

    async def get_companies(self) -> List[models.Company]:
        # Получаем полные сведения об организациях
        """
        stmt = (
            sa_select(models.Company, sa_func.count(models.Card.id).label('cards_amount'))
            .select_from(models.Card)
            .outerjoin(models.Company.cards)
            .group_by(models.Company)
            .order_by(models.Company.name)
            .options(
                selectinload(models.Company.tariff),
                selectinload(models.Company.users).joinedload(models.User.role)
            )
        )
        """
        stmt = (
            sa_select(models.Company)
            .options(
                selectinload(models.Company.balances).selectinload(models.Balance.systems),
                selectinload(models.Company.users).joinedload(models.User.role)
            )
        )
        company_roles = [enums.Role.COMPANY_ADMIN.name, enums.Role.COMPANY_LOGIST.name, enums.Role.COMPANY_DRIVER]
        if self.user.role.name == enums.Role.CARGO_MANAGER.name:
            stmt = stmt.where(models.Company.id.in_(self.user.company_ids_subquery()))

        elif self.user.role.name in company_roles:
            stmt = stmt.where(models.Company.id == self.user.company_id)

        companies = await self.select_all(stmt, scalars=True)
        #companies = list(map(lambda data: data[0].annotate({'cards_amount': data[1]}), dataset))
        # companies = list(map(lambda data: data[0].annotate({'cards_amount': 0}), dataset))

        return companies

    async def get_drivers(self, company_id: str = None) -> models.User:
        stmt = (
            sa_select(models.User)
            .options(
                joinedload(models.User.company),
                joinedload(models.User.role),
            )
            .join(models.User.company)
            .where(models.Role.name == enums.Role.COMPANY_DRIVER.name)
            # .where(models.User.role_id == models.Role.id)
            .order_by(models.Company.name, models.User.last_name, models.User.first_name)
        )
        if company_id:
            stmt = stmt.where(models.User.company_id == company_id)

        drivers = await self.select_all(stmt)
        return drivers

    async def bind_manager(self, company_id: str, user_id: str) -> None:
        new_company_nanager_link = models.AdminCompany(company_id = company_id, user_id = user_id)
        await self.save_object(new_company_nanager_link)

    async def set_company_balance_by_last_transaction(self, balance_id: str) -> Tuple[models.Company, float]:
        # Получаем организацию
        company = await self.get_company_by_balance_id(balance_id)

        # Получаем последнюю транзакцию
        transaction_repository = TransactionRepository(self.session, self.user)
        last_transaction = await transaction_repository.get_last_transaction(balance_id)

        # Устанавливаем текущий баланс организации
        await self.update_object(company, update_data={"balance": last_transaction.company_balance})
        return company, last_transaction.company_balance
