from typing import List

from src.database.model.models import System as SystemOrm
from src.repositories.system import SystemRepository
from src.schemas.system import SystemReadSchema, SystemEditSchema, SystemReadMinimumSchema
from src.utils import enums
from src.utils.exceptions import BadRequestException


class SystemService:

    def __init__(self, repository: SystemRepository) -> None:
        self.repository = repository
        self.logger = repository.logger

    """
    async def create(self, system_create_schema: SystemCreateSchema) -> SystemReadSchema:
        new_system_obj = await self.repository.create(system_create_schema)
        new_system_data = new_system_obj.dumps()
        new_system_data['cards_amount'] = 0
        system_read_schema = SystemReadSchema(**new_system_data)
        return system_read_schema
    """

    """
    async def edit(self, system_id: str, system_edit_schema: SystemEditSchema) -> SystemReadSchema:
        # Получаем систему из БД
        system_obj = await self.repository.session.get(models.System, system_id)
        if not system_obj:
            raise BadRequestException('Запись не найдена')

        # Обновляем данные, сохраняем в БД
        update_data = system_edit_schema.model_dump(exclude_unset=True)
        system_obj.update_without_saving(update_data)
        await self.repository.save_object(system_obj)
        await self.repository.session.refresh(system_obj)

        # Формируем ответ
        updated_system_data = system_obj.dumps()
        updated_system_data['cards_amount'] = await self.repository.get_cards_amount(system_id)
        print('YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY')
        print(updated_system_data)
        system_read_schema = SystemReadSchema(**updated_system_data)

        return system_read_schema
    """

    async def edit(self, system_id: str, system_edit_schema: SystemEditSchema) -> SystemOrm:
        # Получаем систему из БД
        system = await self.repository.get_system(system_id)
        if not system:
            raise BadRequestException('Запись не найдена')

        # Обновляем данные, сохраняем в БД
        update_data = system_edit_schema.model_dump(exclude_unset=True)
        await self.repository.update_object(system, update_data)

        # Формируем ответ
        cards_amount = await self.repository.get_cards_amount(system_id)
        system.annotate({"cards_amount": cards_amount})
        return system

    async def get_systems(self) -> List[SystemReadSchema] | List[SystemReadMinimumSchema]:
        systems = await self.repository.get_systems()

        # Проверка прав доступа.
        # Сотрудникам ПроАВТО отдаем список систем с расширенными данными.
        # Сотрудникам организаций отдаем список систем с минимальным количеством информации.
        major_roles = [enums.Role.CARGO_SUPER_ADMIN.name, enums.Role.CARGO_MANAGER.name, enums.Role.COMPANY_ADMIN.name]
        if self.repository.user.role.name in major_roles:
            system_read_schemas = [SystemReadSchema.model_validate(system) for system in systems]
        else:
            system_read_schemas = [SystemReadMinimumSchema.model_validate(system) for system in systems]

        return system_read_schemas

    """
    async def delete(self, system_id: str) -> None:
        await self.repository.delete_object(models.System, system_id)
    """
