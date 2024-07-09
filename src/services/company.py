from typing import List, Any

from src.database import models
from src.repositories.company import CompanyRepository
from src.repositories.transaction import TransactionRepository
from src.repositories.user import UserRepository
from src.schemas.company import CompanyEditSchema, CompanyReadSchema, CompanyReadMinimumSchema
from src.utils import enums
from src.utils.exceptions import BadRequestException, ForbiddenException


class CompanyService:

    def __init__(self, repository: CompanyRepository) -> None:
        self.repository = repository
        self.logger = repository.logger

    async def edit(self, company_id: str, company_edit_schema: CompanyEditSchema) -> CompanyReadSchema:
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

        # Получаем организацию из БД
        company = await self.repository.session.get(models.Company, company_id)
        print('tariff_id 1', company.tariff_id)
        print('tariff 1', company.tariff)
        if not company:
            raise BadRequestException('Запись не найдена')

        # Обновляем данные, сохраняем в БД
        update_data = company_edit_schema.model_dump(exclude_unset=True)
        if not update_data:
            raise BadRequestException('Отсутствуют данные для обновления')

        await self.repository.update_object(company, update_data)

        # Формируем ответ
        company = await self.repository.get_company(company_id)
        company_read_schema = CompanyReadSchema.model_validate(company)
        return company_read_schema

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

    async def get_companies(self) -> List[Any]:
        # Получаем организации
        companies = await self.repository.get_companies()

        # Отдаем пользователю только ту информацию, которая соответствует его роли
        major_roles = [enums.Role.CARGO_SUPER_ADMIN.name, enums.Role.CARGO_MANAGER.name, enums.Role.COMPANY_ADMIN.name]
        if self.repository.user.role.name in major_roles:
            company_read_schemas = [CompanyReadSchema.model_validate(company) for company in companies]
        else:
            company_read_schemas = [CompanyReadMinimumSchema.model_validate(company) for company in companies]

        return company_read_schemas

    async def get_drivers(self, company_id: str = None) -> models.User:
        drivers = await self.repository.get_drivers(company_id)
        return drivers

    """
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

        # Создаем транзакцию
        transaction_repository = TransactionRepository(self.repository.session, self.repository.user)
        debit = True if edit_balance_schema.direction == enums.Finance.DEBIT.name else False
        await transaction_repository.create_corrective_transaction(company_id, debit, edit_balance_schema.delta_sum)
    """
