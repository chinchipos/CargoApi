from typing import List

from src.database import models
from src.repositories.tariff import TariffRepository
from src.schemas.common import ModelIDSchema
from src.schemas.tariff import TariffCreateSchema, TariffReadSchema, TariffEditSchema
from src.utils.exceptions import BadRequestException


class TariffService:

    def __init__(self, repository: TariffRepository) -> None:
        self.repository = repository
        self.logger = repository.logger

    async def create(self, tariff_create_schema: TariffCreateSchema) -> TariffReadSchema:
        new_tariff_obj = await self.repository.create(tariff_create_schema)
        new_tariff_data = new_tariff_obj.dumps()
        new_tariff_data['companies_amount'] = 0
        tariff_read_schema = TariffReadSchema(**new_tariff_data)
        return tariff_read_schema

    async def edit(self, tariff_id: str, tariff_edit_schema: TariffEditSchema) -> TariffReadSchema:
        # Получаем тариф из БД
        tariff_obj = await self.repository.session.get(models.Tariff, tariff_id)
        if not tariff_obj:
            raise BadRequestException('Запись не найдена')

        # Обновляем данные, сохраняем в БД
        update_data = tariff_edit_schema.model_dump(exclude_unset=True)
        await self.repository.update_object(tariff_obj, update_data)

        # Формируем ответ
        companies_amount = await self.repository.get_companies_amount(tariff_id)
        tariff_obj.annotate({'companies_amount': companies_amount})
        tariff_read_schema = TariffReadSchema.model_validate(tariff_obj)
        return tariff_read_schema

    async def get_tariffs(self) -> List[models.Tariff]:
        tariffs = await self.repository.get_tariffs()
        return tariffs

    async def delete(self, tariff_id: str) -> None:
        await self.repository.delete_object(models.Tariff, tariff_id)
