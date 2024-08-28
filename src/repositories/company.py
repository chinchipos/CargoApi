from datetime import datetime, timedelta
from typing import List, Dict

from sqlalchemy import select as sa_select, and_, func as sa_func, null, or_
from sqlalchemy.orm import joinedload, selectinload, aliased, load_only

from src.config import TZ
from src.database.models import NotificationMailingOrm
from src.database.models.balance import BalanceOrm
from src.database.models.card import CardOrm
from src.database.models.company import CompanyOrm
from src.database.models.user import AdminCompanyOrm, UserOrm
from src.database.models.role import RoleOrm
from src.database.models.balance_system_tariff import BalanceSystemTariffOrm
from src.database.models.system import SystemOrm
from src.database.models.car import CarOrm
from src.database.models.tariff import TariffOrm
from src.database.models.overdrafts_history import OverdraftsHistoryOrm
from src.repositories.base import BaseRepository
from src.repositories.system import SystemRepository
from src.schemas.company import CompanyCreateSchema
from src.utils import enums
from src.utils.common import make_personal_account
from src.utils.enums import ContractScheme, System


class CompanyRepository(BaseRepository):

    async def create(self, company_create_schema: CompanyCreateSchema) -> CompanyOrm:
        # Создаем организацию
        personal_account = make_personal_account()
        company_data = company_create_schema.model_dump()
        # tariffs = company_data.pop("tariffs")
        company = CompanyOrm(**company_data, personal_account=personal_account)
        await self.save_object(company)
        await self.session.refresh(company)

        # Создаем перекупной баланс
        balance = BalanceOrm(
            company_id=company.id,
            scheme=enums.ContractScheme.OVERBOUGHT.name
        )
        await self.save_object(balance)

        # Привязываем перекупной баланс к системам
        system_repository = SystemRepository(session=self.session, user=self.user)
        khnp_system = await system_repository.get_system_by_short_name(
            system_fhort_name=System.KHNP.value,
            scheme=ContractScheme.OVERBOUGHT
        )
        gpn_system = await system_repository.get_system_by_short_name(
            system_fhort_name=System.GPN.value,
            scheme=ContractScheme.OVERBOUGHT
        )

        khnp_bst = BalanceSystemTariffOrm(
            balance_id=balance.id,
            system_id=khnp_system.id,
            tariff_id=None
        )
        await self.save_object(khnp_bst)

        gpn_bst = BalanceSystemTariffOrm(
            balance_id=balance.id,
            system_id=gpn_system.id,
            tariff_id=None
        )
        await self.save_object(gpn_bst)

        # Получаем организацию из БД
        company = await self.get_company(company.id)
        return company

    async def get_khnp_system(self) -> SystemOrm:
        system_repository = SystemRepository(self.session)
        khnp_system = await system_repository.get_system_by_short_name(
            system_fhort_name='ХНП',
            scheme=ContractScheme.OVERBOUGHT
        )
        return khnp_system

    async def get_gpn_system(self) -> SystemOrm:
        system_repository = SystemRepository(self.session)
        khnp_system = await system_repository.get_system_by_short_name(
            system_fhort_name='ГПН',
            scheme=ContractScheme.OVERBOUGHT
        )
        return khnp_system

    async def set_tariff(self, balance_id: str, system_id: str, tariff_id: str) -> None:
        stmt = (
            sa_select(BalanceSystemTariffOrm)
            .where(BalanceSystemTariffOrm.balance_id == balance_id)
            .where(BalanceSystemTariffOrm.system_id == system_id)
        )
        self.statement(stmt)
        bst = await self.select_first(stmt)
        if bst.tariff_id != tariff_id:
            bst.tariff_id = tariff_id
            await self.save_object(bst)

    async def get_company(self, company_id: str) -> CompanyOrm:
        # Получаем сведения об организации
        stmt = (
            sa_select(CompanyOrm)
            .options(
                load_only(
                    CompanyOrm.id,
                    CompanyOrm.name,
                    CompanyOrm.inn,
                    CompanyOrm.min_balance,
                    CompanyOrm.personal_account,
                    CompanyOrm.date_add,
                    CompanyOrm.contacts,
                    CompanyOrm.overdraft_on,
                    CompanyOrm.overdraft_sum,
                    CompanyOrm.overdraft_days,
                    CompanyOrm.overdraft_fee_percent
                )
            )
            .options(
                selectinload(CompanyOrm.balances)
                .load_only(
                    BalanceOrm.id,
                    BalanceOrm.scheme,
                    BalanceOrm.balance
                )
                .selectinload(BalanceOrm.balance_system_tariff)
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
                .load_only(RoleOrm.id, RoleOrm.name, RoleOrm.title, RoleOrm.description)
            )
            .options(
                selectinload(CompanyOrm.cars)
                .load_only(CarOrm.id, CarOrm.model, CarOrm.reg_number)
            )
            .where(CompanyOrm.id == company_id)
        )

        company = await self.select_first(stmt)
        overbought_balance_id = None
        for balance in company.balances:
            systems = []
            for bst in balance.balance_system_tariff:
                bst.system.annotate({"tariff": bst.tariff})
                systems.append(bst.system)
            balance.annotate({"systems": systems})

            if balance.scheme == ContractScheme.OVERBOUGHT:
                overbought_balance_id = balance.id

        # Добавляем сведения об открытых овердрафтах
        today = datetime.now(tz=TZ).date()
        tomorrow = today + timedelta(days=1)
        stmt = (
            sa_select(OverdraftsHistoryOrm)
            .where(OverdraftsHistoryOrm.balance_id == overbought_balance_id)
            .where(or_(
                OverdraftsHistoryOrm.end_date.is_(null()),
                OverdraftsHistoryOrm.end_date >= tomorrow
            ))
        )
        opened_overdraft = await self.select_first(stmt)
        if opened_overdraft:
            overdraft_end_date = opened_overdraft.end_date if opened_overdraft.end_date \
                else opened_overdraft.begin_date + timedelta(days=company.overdraft_days - 1)
            overdraft_payment_deadline = overdraft_end_date + timedelta(days=1)
            company.annotate({
                'overdraft_begin_date': opened_overdraft.begin_date,
                'overdraft_end_date': overdraft_end_date,
                'overdraft_payment_deadline': overdraft_payment_deadline,
            })

        # Добавляем сведения о количестве карт
        # stmt = sa_select(sa_func.count(models.Card.id)).filter_by(company_id=company_id)
        # amount = await self.select_single_field(stmt)
        # company.annotate({'cards_amount': amount})

        # Добавляем непрочитанные рассылки
        if self.user and self.user.role.name == enums.Role.COMPANY_ADMIN.name:
            mailings = await self.get_notification_mailings(company_id=company.id, unread_only=True)
            company.notification_mailings = mailings

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

    async def get_companies(self, filters: Dict[str, str] = None) -> List[CompanyOrm]:
        if filters is None:
            filters = {}

        company_table = aliased(CompanyOrm, name="org")
        helper_cards_amount = (
            sa_select(
                company_table.id.label('company_id'),
                sa_func.count(CardOrm.id).label('cards_amount')
            )
            .join(CardOrm, CardOrm.company_id == company_table.id)
            .group_by(company_table.id)
            .subquery("helper_cards_amount")
        )
        stmt = (
            sa_select(CompanyOrm, BalanceOrm.balance, helper_cards_amount.c.cards_amount)
            .options(
                load_only(
                    CompanyOrm.id,
                    CompanyOrm.name,
                    CompanyOrm.inn,
                    CompanyOrm.personal_account,
                    CompanyOrm.date_add,
                    CompanyOrm.contacts,
                    CompanyOrm.min_balance,
                    CompanyOrm.overdraft_on,
                    CompanyOrm.overdraft_sum,
                    CompanyOrm.overdraft_days,
                    CompanyOrm.overdraft_fee_percent
                )
            )
            .options(
                selectinload(CompanyOrm.balances)
                .load_only(
                    BalanceOrm.id,
                    BalanceOrm.scheme,
                    BalanceOrm.balance
                )
                .selectinload(BalanceOrm.balance_system_tariff)
                .options(
                    joinedload(BalanceSystemTariffOrm.system)
                    .load_only(SystemOrm.id, SystemOrm.full_name)
                )
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
                .load_only(RoleOrm.id, RoleOrm.name, RoleOrm.title, RoleOrm.description)
            )
            .options(
                joinedload(CompanyOrm.tariff_policy)
            )
            .outerjoin(BalanceOrm, and_(
                BalanceOrm.company_id == CompanyOrm.id,
                BalanceOrm.scheme == ContractScheme.OVERBOUGHT
            ))
            .outerjoin(helper_cards_amount, helper_cards_amount.c.company_id == CompanyOrm.id)
            .order_by(BalanceOrm.balance)
            .distinct()
        )
        if filters.get("tariff_policy_id", None):
            stmt = stmt.where(CompanyOrm.tariff_policy_id == filters["tariff_policy_id"])

        company_roles = [enums.Role.COMPANY_ADMIN.name, enums.Role.COMPANY_LOGIST.name, enums.Role.COMPANY_DRIVER]
        if self.user.role.name == enums.Role.CARGO_MANAGER.name:
            company_ids_subquery = self.user.company_ids_subquery()
            stmt = stmt.join(company_ids_subquery, company_ids_subquery.c.id == CompanyOrm.id)

        elif self.user.role.name in company_roles:
            stmt = stmt.where(CompanyOrm.id == self.user.company_id)

        dataset = await self.select_all(stmt, scalars=False)
        companies = [data[0].annotate({"cards_amount": data[2]}) for data in dataset]

        def annotate(company: CompanyOrm) -> CompanyOrm:
            for balance in company.balances:
                systems = []
                for bst in balance.balance_system_tariff:
                    bst.system.annotate({"tariff": bst.tariff})
                    systems.append(bst.system)
                balance.annotate({"systems": systems})
            return company

        companies = list(map(annotate, companies))
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

    async def get_overbought_balance_by_company_id(self, company_id: str) -> BalanceOrm:
        stmt = (
            sa_select(BalanceOrm)
            .where(BalanceOrm.company_id == company_id)
            .where(BalanceOrm.scheme == ContractScheme.OVERBOUGHT)
        )
        balance = await self.select_first(stmt)
        return balance

    async def get_systems_tariffs(self, balance_id: str) -> List[BalanceSystemTariffOrm]:
        stmt = sa_select(BalanceSystemTariffOrm).where(BalanceSystemTariffOrm.balance_id == balance_id)
        bst_list = await self.select_all(stmt)
        return bst_list

    async def get_notification_mailings(self, company_id: str, unread_only: bool = False) -> List[NotificationMailingOrm]:
        stmt = (
            sa_select(NotificationMailingOrm)
            .options(
                joinedload(NotificationMailingOrm.notification)
            )
            .where(NotificationMailingOrm.company_id == company_id)
        )

        if unread_only:
            stmt = stmt.where(NotificationMailingOrm.date_time_read.is_(null()))

        mailings = await self.select_all(stmt)
        return mailings
