from typing import List

from src.database import models
from src.repositories.card import CardRepository
from src.schemas.card import CardCreateSchema, CardReadSchema, CardEditSchema
from src.utils import enums
from src.utils.exceptions import BadRequestException, ForbiddenException


class CardService:

    def __init__(self, repository: CardRepository) -> None:
        self.repository = repository
        self.logger = repository.logger

    async def create(self, card_create_schema: CardCreateSchema) -> CardReadSchema:
        new_card_obj = await self.repository.create(card_create_schema)
        card_obj = await self.repository.get_card(new_card_obj.id)
        card_read_schema = CardReadSchema.model_validate(card_obj)
        return card_read_schema

    async def edit(self, card_id: str, card_edit_schema: CardEditSchema) -> CardReadSchema:
        # Получаем карту из БД
        card_obj = await self.repository.get_card(card_id)
        if not card_obj:
            raise BadRequestException('Запись не найдена')

        # Проверяем права доступа
        # У Суперадмина ПроАВТО есть право в отношении любых сарт
        # У Менеджера ПроАВТО есть прав в отношении карт закрепленных за ним организаций:
        #  >> Менять организацию
        #  >> Привязывать к автомобилю
        #  >> Привязывать к водителю
        #  >> Активировать/блокировать карту
        # У Админа организации есть право в отношении карт своей организации
        #  >> Привязывать к автомобилю
        #  >> Привязывать к водителю
        # У Логиста организации есть право в отношении карт своей организации
        #  >> Привязывать к автомобилю
        #  >> Привязывать к водителю
        # У Водителя нет прав

        current_company_id = card_obj.company_id
        new_company_id = card_edit_schema.company_id

        if self.repository.user.role.name == enums.Role.CARGO_SUPER_ADMIN.name:
            pass

        elif self.repository.user.role.name == enums.Role.CARGO_MANAGER.name:
            # Проверяем права в отношении текущей организации
            if not self.repository.user.is_admin_for_company(current_company_id):
                raise ForbiddenException()

            # Проверяем права в отношении новой организации
            if not self.repository.user.is_admin_for_company(new_company_id):
                raise ForbiddenException()

        elif self.repository.user.role.name in [enums.Role.COMPANY_ADMIN.name, enums.Role.COMPANY_LOGIST.name]:
            # Проверяем права в отношении текущей организации
            if not self.repository.user.is_worker_of_company(current_company_id):
                raise ForbiddenException()

            # Проверяем права в отношении новой организации
            if not self.repository.user.is_worker_of_company(new_company_id):
                raise ForbiddenException()

        else:
            raise ForbiddenException()

        # Полученную модель с данными преобразуем в словарь
        temporary_update_data = card_edit_schema.model_dump(exclude_unset=True)

        # В зависимости от роли убираем возможность редактирования некоторых полей
        if self.repository.user.role.name == enums.Role.CARGO_MANAGER.name:
            allowed_fields = ['company_id', 'belongs_to_car_id', 'belongs_to_driver_id', 'is_active']
            update_data = {k: v for k, v in temporary_update_data.items() if k in allowed_fields}

        elif self.repository.user.role.name in [enums.Role.COMPANY_ADMIN.name, enums.Role.COMPANY_LOGIST.name]:
            allowed_fields = ['belongs_to_car_id', 'belongs_to_driver_id']
            update_data = {k: v for k, v in temporary_update_data.items() if k in allowed_fields}

        else:
            update_data = temporary_update_data

        # Обновляем запись в БД
        await self.repository.update_model_instance(card_obj, update_data)

        # Формируем ответ
        card_read_schema = CardReadSchema.model_validate(card_obj)

        return card_read_schema

    async def get_cards(self) -> List[models.Card]:
        cards = await self.repository.get_cards()
        return cards

    async def delete(self, card_id: str) -> None:
        await self.repository.delete_one(models.Card, card_id)
