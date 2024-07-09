from typing import List

from src.database import models
from src.repositories.system import SystemRepository
from src.schemas.system import SystemReadSchema, SystemEditSchema
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
        system_read_schema = SystemReadSchema(**updated_system_data)
        return system_read_schema

    async def get_systems(self) -> List[models.System]:
        systems = await self.repository.get_systems()
        return systems

    """
    async def delete(self, system_id: str) -> None:
        await self.repository.delete_object(models.System, system_id)
    """
