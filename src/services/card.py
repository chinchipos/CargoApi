from typing import List

from src.database.model.models import CardSystem as CardSystemOrm
from src.database.model.card import CardOrm
from src.repositories.card import CardRepository
from src.schemas.card import CardCreateSchema, CardReadSchema, CardEditSchema
from src.utils import enums
from src.utils.exceptions import BadRequestException, ForbiddenException


class CardService:

    def __init__(self, repository: CardRepository) -> None:
        self.repository = repository
        self.logger = repository.logger

    async def get_card(self, card_id: str) -> CardOrm:
        card = await self.repository.get_card(card_id)
        if not card:
            raise BadRequestException('Запись не найдена')
        return card

    async def create(self, card_create_schema: CardCreateSchema, systems: List[str] | None) -> CardReadSchema:
        # Создаем карту
        new_card_obj = await self.repository.create(card_create_schema)

        # Привязываем к системам
        await self.binding_systems(
            card_id=new_card_obj.id,
            current_systems=[],
            new_systems=systems
        )

        # Получаем полную информацию о карте
        card_obj = await self.repository.get_card(new_card_obj.id)

        # Формируем ответ
        card_read_schema = CardReadSchema.model_validate(card_obj)
        return card_read_schema

    async def edit(self, card_id: str, card_edit_schema: CardEditSchema, systems: List[str]) -> CardOrm:
        # Получаем карту из БД
        card = await self.get_card(card_id)

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

        current_company_id = card.company_id
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
        await self.repository.update_object(card, update_data)

        # Отвязываем от неактуальных систем, привязываем к новым
        await self.binding_systems(
            card_id=card.id,
            current_systems=[system.id for system in card.systems],
            new_systems=systems
        )

        # Получаем карту из БД
        card = await self.get_card(card_id)
        return card

    async def get_cards(self) -> List[CardOrm]:
        cards = await self.repository.get_cards()
        return cards

    async def delete(self, card_id: str) -> None:
        # Проверяем наличие транзакций по карте
        has_transactions = await self.repository.has_transactions(card_id)

        if has_transactions:
            raise BadRequestException("Невозможно удалить карту, так как по ней были транзакции.")

        # Открепляем карту от других объектов и удаляем её саму
        await self.repository.delete(card_id)

    async def binding_systems(self, card_id: str, current_systems: List[str], new_systems: List[str]) -> None:
        systems_to_unbind = [pk for pk in current_systems if pk not in new_systems]
        await self.repository.unbind_systems(card_id, systems_to_unbind)

        systems_to_bind = [pk for pk in new_systems if pk not in current_systems]
        await self.repository.bind_systems(card_id, systems_to_bind)

    async def bulk_bind_company(self, card_numbers: List[str], company_id: str) -> None:
        # Получаем из БД карты по списку номеров
        cards = await self.repository.get_cards(card_numbers=card_numbers)

        # Проверяем права доступа
        # У Суперадмина ПроАВТО есть право в отношении любых сарт.
        # У Менеджера ПроАВТО есть права в отношении карт закрепленных за ним организаций.
        # У остальных ролей нет прав.
        if self.repository.user.role.name == enums.Role.CARGO_SUPER_ADMIN.name:
            pass

        elif self.repository.user.role.name == enums.Role.CARGO_MANAGER.name:
            # Проверка прав доступа к картам. В списке их и так не должно появиться, так как функция выше эту
            # проверку и так осуществляет. Но для красоты пусть будет.
            for card in cards:
                if not card.company_id or not self.repository.user.is_admin_for_company(card.company_id):
                    raise ForbiddenException()

            if not self.repository.user.is_admin_for_company(company_id):
                raise ForbiddenException()

        else:
            raise ForbiddenException()

        # Выполняем привязку к организации
        dataset = [{"id": card.id, "company_id": company_id} for card in cards]
        await self.repository.bulk_update(CardOrm, dataset)

    async def bulk_bind_systems(self, card_numbers: List[str], system_ids: List[str]) -> None:
        # Проверяем права доступа.
        # У Суперадмина ПроАВТО есть право в отношении любых сарт.
        # У остальных ролей нет прав.
        if self.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
            raise ForbiddenException()

        # Получаем из БД карты по списку номеров
        cards = await self.repository.get_cards(card_numbers=card_numbers)

        # Получаем из БД системы по списку идентификаторов. Это нужно, чтобы убедиться, что
        # полученные идентификаторы указывают на реальные записи.
        systems = await self.repository.get_systems(system_ids=system_ids)

        # Прикрепляем карты к полученным системам (ранее привязанные системы не удаляются)
        for card in cards:
            current_system_ids = [system.id for system in card.systems]
            for system in systems:
                if system.id not in current_system_ids:
                    cs_fields = dict(
                        card_id=card.id,
                        system_id=system.id,
                    )
                    await self.repository.insert(CardSystemOrm, **cs_fields)

    async def bulk_bind(self, card_numbers: List[str], company_id: str, system_ids: List[str]) -> None:
        if company_id:
            await self.bulk_bind_company(card_numbers, company_id)

        if system_ids:
            await self.bulk_bind_systems(card_numbers, system_ids)

    async def bulk_unbind_company(self, card_numbers: List[str]) -> None:
        # Получаем из БД карты по списку номеров
        cards = await self.repository.get_cards(card_numbers=card_numbers)

        # Проверяем права доступа к каждой карте.
        # У Суперадмина ПроАВТО есть право в отношении любых сарт.
        # У Менеджера ПроАВТО есть права в отношении карт закрепленных за ним организаций.
        # У остальных ролей нет прав.
        if self.repository.user.role.name == enums.Role.CARGO_SUPER_ADMIN.name:
            pass

        elif self.repository.user.role.name == enums.Role.CARGO_MANAGER.name:
            # Проверка прав доступа к картам. В списке их и так не должно появиться, так как функция выше эту
            # проверку и так осуществляет. Но для красоты пусть будет.
            for card in cards:
                if not card.company_id or not self.repository.user.is_admin_for_company(card.company_id):
                    raise ForbiddenException()

        else:
            raise ForbiddenException()

        # Отвязываем от карт автомобиль, водителя, организацию. Блокируем карту.
        dataset = [
            {
                "id": card.id,
                "company_id": None,
                "belongs_to_car_id": None,
                "belongs_to_driver_id": None,
                "is_active": False,
            } for card in cards
        ]
        await self.repository.bulk_update(CardOrm, dataset)

    async def bulk_unbind_systems(self, card_numbers: List[str]) -> None:
        if not card_numbers:
            return

        # Проверяем права доступа.
        # У Суперадмина ПроАВТО есть право в отношении любых сарт.
        # У остальных ролей нет прав.
        if self.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
            raise ForbiddenException()

        # Открепляем карты от систем
        await self.repository.bulk_unbind_systems(card_numbers=card_numbers)

    async def bulk_activate(self, card_numbers: List[str]) -> None:
        # Получаем из БД карты по списку номеров
        cards = await self.repository.get_cards(card_numbers=card_numbers)

        # Проверяем права доступа.
        # У Суперадмина ПроАВТО есть право в отношении любых сарт.
        # У менеджера ПроАВТО права в отношении своих организаций.
        # У остальных ролей нет прав.
        if self.repository.user.role.name == enums.Role.CARGO_SUPER_ADMIN.name:
            pass

        elif self.repository.user.role.name != enums.Role.CARGO_MANAGER.name:
            for card in cards:
                if not card.company_id or not self.repository.user.is_admin_for_company(card.company_id):
                    raise ForbiddenException()

        else:
            raise ForbiddenException()

        # Разблокируем карты
        dataset = [{"id": card.id, "is_active": True, "manual_lock": False} for card in cards]
        await self.repository.bulk_update(CardOrm, dataset)

    async def bulk_block(self, card_numbers: List[str]) -> None:
        # Получаем из БД карты по списку номеров
        cards = await self.repository.get_cards(card_numbers=card_numbers)

        # Проверяем права доступа.
        # У Суперадмина ПроАВТО есть право в отношении любых сарт.
        # У менеджера ПроАВТО права в отношении своих организаций.
        # У администратора организации есть права в отношении своей организации.
        # У остальных ролей нет прав.
        if self.repository.user.role.name == enums.Role.CARGO_SUPER_ADMIN.name:
            pass

        elif self.repository.user.role.name != enums.Role.CARGO_MANAGER.name:
            for card in cards:
                if not card.company_id or not self.repository.user.is_admin_for_company(card.company_id):
                    raise ForbiddenException()

        elif self.repository.user.role.name != enums.Role.COMPANY_ADMIN.name:
            for card in cards:
                if not self.repository.user.is_worker_of_company(card.company_id):
                    raise ForbiddenException()

        else:
            raise ForbiddenException()

        # Блокируем карты
        dataset = [{"id": card.id, "is_active": False, "manual_lock": True} for card in cards]
        await self.repository.bulk_update(CardOrm, dataset)
