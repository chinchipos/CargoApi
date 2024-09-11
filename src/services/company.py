from datetime import datetime
from typing import List, Any, Dict

from src.celery_app.gpn.tasks import gpn_update_group_limits
from src.celery_app.group_limit_order import GroupLimitOrder
from src.config import TZ
from src.database.models import BalanceOrm, BalanceSystemOrm
from src.database.models.company import CompanyOrm
from src.database.models.notification import NotificationMailingOrm
from src.database.models.user import UserOrm
from src.repositories.company import CompanyRepository
from src.repositories.system import SystemRepository
from src.repositories.tariff import TariffRepository
from src.repositories.transaction import TransactionRepository
from src.repositories.user import UserRepository
from src.schemas.company import CompanyEditSchema, CompanyReadSchema, CompanyReadMinimumSchema, \
    CompanyBalanceEditSchema, CompanyCreateSchema
from src.utils import enums
from src.utils.common import make_personal_account, calc_available_balance
from src.utils.enums import TransactionType
from src.utils.exceptions import BadRequestException, ForbiddenException


class CompanyService:

    def __init__(self, repository: CompanyRepository) -> None:
        self.repository = repository
        self.logger = repository.logger

    async def create(self, company_create_schema: CompanyCreateSchema) -> CompanyOrm:
        # Создаем организацию
        personal_account = make_personal_account()
        company_data = company_create_schema.model_dump()
        company = CompanyOrm(**company_data, personal_account=personal_account)
        await self.repository.save_object(company)
        await self.repository.session.refresh(company)

        # Создаем перекупной баланс
        balance = BalanceOrm(
            company_id=company.id,
            scheme=enums.ContractScheme.OVERBOUGHT.name
        )
        await self.repository.save_object(balance)

        # Привязываем перекупной баланс к системам
        system_repository = SystemRepository(session=self.repository.session, user=self.repository.user)
        systems = await system_repository.get_systems()
        for system in systems:
            if system.enabled:
                balance_system = BalanceSystemOrm(balance_id=balance.id, system_id=system.id)
                await self.repository.save_object(balance_system)

        # Получаем организацию из БД
        company = await self.get_company(company.id)
        return company

    async def edit(self, company_id: str, company_edit_schema: CompanyEditSchema) -> CompanyOrm:
        # Проверка прав доступа.
        # У суперадмина ПроАВТО полные права.
        # У Менеджера ПроАВТО права только в отношении своих организаций.
        # У остальных ролей нет прав.
        if self.repository.user.role.name == enums.Role.CARGO_SUPER_ADMIN.name:
            pass

        elif self.repository.user.role.name == enums.Role.CARGO_MANAGER.name:
            if not self.repository.user.is_admin_for_company(company_id):
                raise ForbiddenException()

        else:
            raise ForbiddenException()

        # Проверяем входные данные
        if company_edit_schema.overdraft_on:
            # Если активирован овердрафт, то обязательно должны быть заполнены поля: сумма, дни
            if company_edit_schema.overdraft_sum is None:
                raise BadRequestException("Не указана сумма овердрафта")

            if not company_edit_schema.overdraft_days:
                raise BadRequestException("Не указан срок овердрафта")

            if not company_edit_schema.overdraft_fee_percent:
                raise BadRequestException("Не указан размер комиссии за овердрафт")

        else:
            company_edit_schema.overdraft_on = False
            company_edit_schema.overdraft_sum = 0
            company_edit_schema.overdraft_days = 0
            company_edit_schema.overdraft_fee_percent = 0.074

        # Получаем организацию из БД
        company = await self.repository.get_company(company_id)
        if not company:
            raise BadRequestException('Запись не найдена')

        # Вычисляем доступный баланс до применения изменений
        available_balance_before = calc_available_balance(
            current_balance=company.overbought_balance().balance,
            min_balance=company.min_balance,
            overdraft_on=company.overdraft_on,
            overdraft_sum=company.overdraft_sum
        )

        # Обновляем данные, сохраняем в БД
        update_data = company_edit_schema.model_dump(exclude_unset=True)
        if not update_data:
            raise BadRequestException('Отсутствуют данные для обновления')

        await self.repository.update_object(company, update_data)

        company = await self.repository.get_company(company_id)

        # Вычисляем доступный баланс после применения изменений
        available_balance_after = calc_available_balance(
            current_balance=company.overbought_balance().balance,
            min_balance=company.min_balance,
            overdraft_on=company.overdraft_on,
            overdraft_sum=company.overdraft_sum
        )

        # Если доступный баланс изменился, то обновляем лимит в системе ГПН.
        # Проверка на предмет наличия карт этой системы будет выполнена на следующем этапе.
        order = GroupLimitOrder(
            personal_account=company.personal_account,
            delta_sum=available_balance_after - available_balance_before
        )
        gpn_update_group_limits.delay([order])

        return company

    async def bind_manager(self, company_id: str, user_id: str) -> None:
        # Назначаемый менеджер обязан обладать соответствующей ролью
        user_repository = UserRepository(self.repository.session, self.repository.user)
        manager = await user_repository.get_user(user_id)
        if manager.role.name != enums.Role.CARGO_MANAGER.name:
            raise ForbiddenException()

        await self.repository.bind_manager(company_id, user_id)

    async def get_company(self, company_id: str) -> Any:
        # Получаем организацию
        company = await self.repository.get_company(company_id)
        # Отдаем пользователю только ту информацию, которая соответствует его роли
        major_roles = [enums.Role.CARGO_SUPER_ADMIN.name, enums.Role.CARGO_MANAGER.name, enums.Role.COMPANY_ADMIN.name]
        if self.repository.user.role.name in major_roles:
            company_read_schema = CompanyReadSchema.model_validate(company)
        else:
            company_read_schema = CompanyReadMinimumSchema.model_validate(company)

        return company_read_schema

    async def get_companies(self, with_dictionaries: bool, filters: Dict[str, str]) -> Dict[str, Any]:
        # Получаем организации
        companies = await self.repository.get_companies(filters=filters)
        # Отдаем пользователю только ту информацию, которая соответствует его роли
        major_roles = [enums.Role.CARGO_SUPER_ADMIN.name, enums.Role.CARGO_MANAGER.name, enums.Role.COMPANY_ADMIN.name]
        if self.repository.user.role.name in major_roles:
            companies_read_schema = [CompanyReadSchema.model_validate(company) for company in companies]
        else:
            companies_read_schema = [CompanyReadMinimumSchema.model_validate(company) for company in companies]

        dictionaries = None
        if with_dictionaries:
            # Тарифные политики
            tariff_repository = TariffRepository(session=self.repository.session, user=self.repository.user)
            tariff_polices = await tariff_repository.get_tariff_polices_without_tariffs()

            dictionaries = {
                "tariff_polices": tariff_polices,
            }

        data = {
            "companies": companies_read_schema,
            "dictionaries": dictionaries
        }

        return data

    async def get_drivers(self, company_id: str = None) -> UserOrm:
        drivers = await self.repository.get_drivers(company_id)
        return drivers

    async def edit_company_balance(self, company_id: str, edit_balance_schema: CompanyBalanceEditSchema) -> None:
        # Проверка прав доступа.
        # У суперадмина ПроАВТО полные права.
        # У Менеджера ПроАВТО права только в отношении своих организаций.
        # У остальных ролей нет прав.
        if self.repository.user.role.name == enums.Role.CARGO_SUPER_ADMIN.name:
            pass

        elif self.repository.user.role.name == enums.Role.CARGO_MANAGER.name:
            if not self.repository.user.is_admin_for_company(company_id):
                raise ForbiddenException()

        else:
            raise ForbiddenException()

        # Получаем перекупной баланс
        company = await self.repository.get_company(company_id)
        balance = company.overbought_balance()

        # Создаем транзакцию
        transaction_repository = TransactionRepository(self.repository.session, self.repository.user)
        transaction_type = TransactionType.DECREASE if edit_balance_schema.direction == enums.Finance.DEBIT.name \
            else TransactionType.REFILL

        await transaction_repository.create_corrective_transaction(
            balance=balance,
            transaction_type=transaction_type,
            delta_sum=edit_balance_schema.delta_sum
        )

        # Обновляем лимит в системе ГПН.
        # Проверка на предмет наличия карт этой системы будет выполнена на следующем этапе.
        delta_sum = edit_balance_schema.delta_sum if transaction_type == TransactionType.REFILL \
            else -edit_balance_schema.delta_sum
        order = GroupLimitOrder(
            personal_account=company.personal_account,
            delta_sum=delta_sum
        )
        gpn_update_group_limits.delay([order])

    async def get_notifications(self) -> List[NotificationMailingOrm]:
        mailings = await self.repository.get_notification_mailings(self.repository.user.company_id)
        # for mailing in mailings:
        #     mailing.annotate({
        #         "date_create": mailing.notification.date_create,
        #         "caption": mailing.notification.caption,
        #         "text": mailing.notification.text,
        #     })
        return mailings

    async def notification_read(self, mailing_id: str) -> None:
        notification_mailing = await self.repository.session.get(NotificationMailingOrm, mailing_id)
        notification_mailing.date_time_read = datetime.now(tz=TZ)
        await self.repository.save_object(notification_mailing)
