from typing import List, Any

from src.database import models
from src.repositories.company import CompanyRepository
from src.schemas.company import CompanyEditSchema, CompanyReadSchema, CompanyReadMinimumSchema
from src.utils import enums
from src.utils.exceptions import BadRequestException


class CompanyService:

    def __init__(self, repository: CompanyRepository) -> None:
        self.repository = repository
        self.logger = repository.logger

    async def edit(self, company_id: str, company_edit_schema: CompanyEditSchema) -> CompanyReadSchema:
        # Получаем организацию из БД
        company_obj = await self.repository.session.get(models.Company, company_id)
        if not company_obj:
            raise BadRequestException('Запись не найдена')

        # Обновляем данные, сохраняем в БД
        update_data = company_edit_schema.model_dump(exclude_unset=True)
        await self.repository.update_model_instance(company_obj, update_data)

        # Формируем ответ
        company = await self.repository.get_company(company_id)
        company_read_schema = CompanyReadSchema.model_validate(company)
        return company_read_schema

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
