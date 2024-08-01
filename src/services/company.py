from typing import List, Any

from src.database.model.models import Company as CompanyOrm, User as UserOrm
from src.repositories.company import CompanyRepository
from src.repositories.transaction import TransactionRepository
from src.repositories.user import UserRepository
from src.schemas.company import CompanyEditSchema, CompanyReadSchema, CompanyReadMinimumSchema, \
    CompanyBalanceEditSchema, CompanyCreateSchema
from src.utils import enums
from src.utils.enums import TransactionType
from src.utils.exceptions import BadRequestException, ForbiddenException


class CompanyService:

    def __init__(self, repository: CompanyRepository) -> None:
        self.repository = repository
        self.logger = repository.logger

    async def create(self, company_create_schema: CompanyCreateSchema) -> CompanyOrm:
        company = await self.repository.create(company_create_schema)
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

        # Обновляем данные, сохраняем в БД
        update_data = company_edit_schema.model_dump(exclude_unset=True)
        if not update_data:
            raise BadRequestException('Отсутствуют данные для обновления')

        await self.repository.update_object(company, update_data)

        company = await self.repository.get_company(company_id)

        # Получаем перекупной баланс
        balance = None
        for cb in company.balances:
            if cb.scheme == enums.ContractScheme.OVERBOUGHT:
                balance = cb
                break

        # Получаем систему ХНП
        khnp_system = await self.repository.get_khnp_system()

        # Устанавливаем тариф
        await self.repository.set_tariff(
            balance_id=balance.id,
            system_id=khnp_system.id,
            tariff_id=company_edit_schema.tariff_id
        )

        # Формируем ответ
        company = await self.repository.get_company(company_id)
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

    async def get_companies(self) -> List[CompanyReadSchema] | List[CompanyReadMinimumSchema]:
        # Получаем организации
        companies = await self.repository.get_companies()
        # Отдаем пользователю только ту информацию, которая соответствует его роли
        major_roles = [enums.Role.CARGO_SUPER_ADMIN.name, enums.Role.CARGO_MANAGER.name, enums.Role.COMPANY_ADMIN.name]
        if self.repository.user.role.name in major_roles:
            company_read_schemas = [CompanyReadSchema.model_validate(company) for company in companies]
        else:
            company_read_schemas = [CompanyReadMinimumSchema.model_validate(company) for company in companies]

        return company_read_schemas

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

        # Получаем перекупной баланс организации (он может быть всего 1 у организации)
        balance = await self.repository.get_overbought_balance_by_company_id(company_id)
        # Создаем транзакцию
        transaction_repository = TransactionRepository(self.repository.session, self.repository.user)
        transaction_type = TransactionType.DECREASE if edit_balance_schema.direction == enums.Finance.DEBIT.name \
            else TransactionType.REFILL
        await transaction_repository.create_corrective_transaction(
            balance=balance,
            transaction_type=transaction_type,
            delta_sum=edit_balance_schema.delta_sum
        )
