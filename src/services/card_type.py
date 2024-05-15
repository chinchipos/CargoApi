from typing import List

from src.database import models
from src.repositories.card_type import CardTypeRepository
from src.schemas.common import ModelIDSchema
from src.schemas.card_type import CardTypeCreateSchema, CardTypeReadSchema, CardTypeEditSchema
from src.utils.exceptions import BadRequestException


class CardTypeService:

    def __init__(self, repository: CardTypeRepository) -> None:
        self.repository = repository
        self.logger = repository.logger

    async def create(self, card_type_create_schema: CardTypeCreateSchema) -> CardTypeReadSchema:
        new_card_type_obj = await self.repository.create(card_type_create_schema)
        card_type_read_schema = CardTypeReadSchema.model_validate(new_card_type_obj)
        return card_type_read_schema

    async def edit(self, card_type_edit_schema: CardTypeEditSchema) -> CardTypeReadSchema:
        # Получаем запись из БД
        card_type_obj = await self.repository.session.get(models.CardType, card_type_edit_schema.id)
        if not card_type_obj:
            raise BadRequestException('Запись не найдена')

        # Обновляем данные, сохраняем в БД
        update_data = card_type_edit_schema.model_dump(exclude_unset=True)
        card_type_obj.update_without_saving(update_data)
        self.repository.session.add(card_type_obj)
        await self.repository.session.commit()
        await self.repository.session.refresh(card_type_obj)

        # Формируем ответ
        card_type_read_schema = CardTypeReadSchema.model_validate(card_type_obj)
        return card_type_read_schema

    async def get_card_types(self) -> List[models.CardType]:
        card_types = await self.repository.get_card_types()
        return card_types

    async def delete(self, data: ModelIDSchema) -> None:
        await self.repository.delete_one(models.CardType, data.id)
