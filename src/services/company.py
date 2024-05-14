from typing import List, Any

from src.database import models
from src.repositories.company import CompanyRepository
from src.schemas.company import CompanyEditSchema, CompanyReadSchema, CompanyReadLowRightsSchema
from src.utils import enums
from src.utils.exceptions import BadRequestException


class CompanyService:

    def __init__(self, repository: CompanyRepository) -> None:
        self.repository = repository
        self.logger = repository.logger

    async def edit(self, company_edit_schema: CompanyEditSchema) -> CompanyReadSchema:
        # Получаем организацию из БД
        company_obj = await self.repository.session.get(models.Company, company_edit_schema.id)
        if not company_obj:
            raise BadRequestException('Запись не найдена')

        # Обновляем данные, сохраняем в БД
        update_data = company_edit_schema.model_dump(exclude_unset=True)
        company_obj.update_without_saving(update_data)
        self.repository.session.add(company_obj)
        self.repository.session.commit()
        self.repository.session.refresh(company_obj)

        # Формируем ответ
        company = await self.repository.get_company(company_obj.id)
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
            company_read_schema = CompanyReadLowRightsSchema.model_validate(company)

        return company_read_schema

    async def get_companies(self) -> List[Any]:
        # Получаем организации
        companies = await self.repository.get_companies()

        # Отдаем пользователю только ту информацию, которая соответствует его роли
        major_roles = [enums.Role.CARGO_SUPER_ADMIN.name, enums.Role.CARGO_MANAGER.name, enums.Role.COMPANY_ADMIN.name]
        if self.repository.user.role.name in major_roles:
            company_read_schemas = [CompanyReadSchema.model_validate(company) for company in companies]
        else:
            company_read_schemas = [CompanyReadLowRightsSchema.model_validate(company) for company in companies]

        return company_read_schemas
