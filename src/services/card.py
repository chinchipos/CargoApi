import math
from typing import List

from src.celery_app.gpn.tasks import gpn_cards_bind_company, gpn_cards_unbind_company, gpn_set_card_state, \
    gpn_delete_card_limits, gpn_create_card_limits
from src.celery_app.khnp.tasks import khnp_set_card_state
from src.database.models import CompanyOrm
from src.database.models.card import CardOrm, BlockingCardReason
from src.database.models.card_limit import Unit, LimitPeriod, CardLimitOrm
from src.database.models.goods_category import GoodsCategory
from src.database.models.system import CardSystemOrm
from src.repositories.card import CardRepository
from src.repositories.company import CompanyRepository
from src.repositories.goods import GoodsRepository
from src.schemas.card import CardCreateSchema, CardReadSchema, CardEditSchema
from src.schemas.card_limit import CardLimitParamsSchema, CardLimitCreateSchema
from src.utils import enums
from src.utils.common import calc_available_balance
from src.utils.enums import ContractScheme
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

    @staticmethod
    def available_balance(company: CompanyOrm) -> float:
        for balance in company.balances:
            if balance.scheme == ContractScheme.OVERBOUGHT:
                return calc_available_balance(
                    current_balance=balance.balance,
                    min_balance=company.min_balance,
                    overdraft_on=company.overdraft_on,
                    overdraft_sum=company.overdraft_sum
                )

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
        card_update_data = card_edit_schema.model_dump(exclude_unset=True)

        if current_company_id != new_company_id:
            card_update_data['group_id'] = None

        # В зависимости от роли убираем возможность редактирования некоторых полей
        if self.repository.user.role.name == enums.Role.CARGO_MANAGER.name:
            allowed_fields = ['company_id', 'belongs_to_car_id', 'belongs_to_driver_id', 'is_active']
            update_data = {k: v for k, v in card_update_data.items() if k in allowed_fields}

        elif self.repository.user.role.name in [enums.Role.COMPANY_ADMIN.name, enums.Role.COMPANY_LOGIST.name]:
            allowed_fields = ['belongs_to_car_id', 'belongs_to_driver_id', 'limit_sum', 'limit_volume']
            update_data = {k: v for k, v in card_update_data.items() if k in allowed_fields}

        else:
            update_data = card_update_data

        # Обновляем запись в БД
        await self.repository.update_object(card, update_data)

        # Отвязываем от неактуальных систем, привязываем к новым
        await self.binding_systems(
            card_id=card.id,
            current_systems=[system.id for system in card.systems],
            new_systems=systems
        )

        # Получаем карту из БД
        card = await self.repository.get_card(card_id)

        # Если карта ГПН, то назначаем ей группу
        for system in card.systems:
            if system.short_name == 'ГПН':
                if current_company_id != new_company_id:
                    if new_company_id:
                        company_repository = CompanyRepository(session=self.repository.session)
                        company = await company_repository.get_company(new_company_id)
                        company_available_balance = self.available_balance(company)

                        # gpn_cards_bind_company.delay(
                        #     card_ids=[card.id],
                        #     personal_account=card.company.personal_account,
                        #     company_available_balance=company_available_balance
                        # )

                    else:
                        # gpn_cards_unbind_company.delay([card.id])
                        pass

                break

        # Получаем карту из БД
        card = await self.repository.get_card(card_id)
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

        # Если карта ГПН, то назначаем ей группу
        card_ids = []
        for card in cards:
            for system in card.systems:
                if system.short_name == 'ГПН':
                    card_ids.append(card.id)
                    break

        if card_ids:
            company_repository = CompanyRepository(session=self.repository.session)
            company = await company_repository.get_company(company_id)
            limit_sum = 1
            for balance in company.balances:
                if balance.scheme == ContractScheme.OVERBOUGHT:
                    # Вычисляем доступный лимит
                    overdraft_sum = company.overdraft_sum if company.overdraft_on else 0
                    boundary_sum = company.min_balance - overdraft_sum
                    limit_sum = abs(boundary_sum - balance.balance) if boundary_sum < balance.balance else 1
                    break

            gpn_cards_bind_company.delay(card_ids, company.personal_account, limit_sum)

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

        # Отвязываем от карт автомобиль, водителя, организацию, группу. Блокируем карту.
        dataset = [
            {
                "id": card.id,
                "company_id": None,
                "belongs_to_car_id": None,
                "belongs_to_driver_id": None,
                "group_id": None,
                "is_active": False,
            } for card in cards
        ]
        await self.repository.bulk_update(CardOrm, dataset)

        card_ids = []
        for card in cards:
            for system in card.systems:
                if system.short_name == 'ГПН':
                    card_ids.append(card.id)
                    break

        if card_ids:
            gpn_cards_unbind_company.delay(card_ids)

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

    async def set_state(self, card_id: str, activate: bool) -> None:
        # Получаем карту
        card = await self.repository.get_card(card_id)

        # Если карта заблокирована нами автоматически или вручную, то разблокировать её может либо суперадмин,
        # либо менеджер ПроАВТО
        cargo_roles = [enums.Role.CARGO_SUPER_ADMIN.name, enums.Role.CARGO_MANAGER.name]
        if not card.is_active and card.reason_for_blocking == BlockingCardReason.NNK \
                and activate and self.repository.user.role.name not in cargo_roles:
            raise ForbiddenException()

        # Если карта заблокирована по ПИН, то ее нельзя разблокировать программным способом
        if not card.is_active and card.reason_for_blocking == BlockingCardReason.PIN and activate:
            raise BadRequestException(message="Карта заблокирована по ПИН. Нельзя её разблокировать программно.")

        # Меняем состояние карты
        if card.is_active != activate:
            card.is_active = activate
            await self.repository.save_object(card)

            # Отправляем в Celery задачу на установку состояния карты в соответствующей системе
            for system in card.systems:
                if system.short_name == enums.System.KHNP.value:
                    khnp_set_card_state.delay(card.card_number, card.is_active)
                elif system.short_name == enums.System.GPN.value:
                    gpn_set_card_state.delay(card.external_id, card.is_active)

    async def get_limit_params(self) -> CardLimitParamsSchema:
        # Получаем список групп продуктов нашей системы
        goods_repository = GoodsRepository(session=self.repository.session, user=self.repository.user)
        inner_groups = await goods_repository.get_inner_groups()

        # Формируем справочник "Категория -> Продукты"
        categories = [
            {
                "id": category.name,
                "name": category.value,
                "groups": [group for group in inner_groups if group.inner_category == category]
            } for category in GoodsCategory
        ]

        # Формируем справочник единиц измерения
        units = [
            {"id": Unit.ITEMS.name, "name": Unit.ITEMS.value, "type": "base"},
            {"id": Unit.LITERS.name, "name": Unit.LITERS.value, "type": "base"},
            {"id": Unit.RUB.name, "name": Unit.RUB.value, "type": "addable"},
        ]

        # Формируем справочник периодов
        periods = [
            {"id": LimitPeriod.MONTH.name, "name": LimitPeriod.MONTH.value},
            {"id": LimitPeriod.DAY.name, "name": LimitPeriod.DAY.value},
        ]

        # Формируем выходную структуру
        limit_params_data = {
            "categories": categories,
            "units": units,
            "periods": periods,
        }
        limit_params = CardLimitParamsSchema(**limit_params_data)
        return limit_params

    async def set_limits(self, card: CardOrm, limits: List[CardLimitCreateSchema]) -> List[CardLimitOrm]:
        # Оптимизируем полученные лимиты - убираем избыточные и дублирующиеся
        received_limits: List[CardLimitCreateSchema] = []
        while len(limits) > 0:
            limit = limits[0]
            found = False
            for unique_limit in received_limits:
                if limit.inner_goods_category == unique_limit.inner_goods_category \
                        and limit.inner_goods_group_id == unique_limit.inner_goods_group_id \
                        and limit.period == unique_limit.period and limit.unit == unique_limit.unit:

                    found = True
                    # Сравниваем суммы. Оставляем только одну из записей.
                    if limit.value < unique_limit.value:
                        unique_limit.value = limit.value

                    break

            if not found:
                received_limits.append(limit)

            limits.remove(limit)

        # Получаем доступный баланс организации
        company_repository = CompanyRepository(session=self.repository.session, user=self.repository.user)
        # company = await company_repository.get_company(card.company_id)
        # company_available_balance = self.available_balance(company)

        # Все рублевые лимиты не должны превышать доступный баланс организации
        # for limit in received_limits:
        #     print(limit.value)
        #     if limit.value > company_available_balance:
        #         limit.value = int(math.floor(company_available_balance))

        # Получаем действующие лимиты
        limits_to_delete = await self.repository.get_limits(card_id=card.id)

        # Удаляем из БД действующие лимиты
        await self.repository.delete_card_limits(card_id=card.id)

        # Сохраняем в БД новые лимиты
        new_limits = [
            {
                "card_id": card.id,
                "value": limit.value,
                "unit": limit.unit,
                "period": limit.period,
                "inner_goods_group_id": limit.inner_goods_group_id,
                "inner_goods_category": limit.inner_goods_category,
            } for limit in received_limits
        ]
        await self.repository.bulk_insert_or_update(CardLimitOrm, new_limits)

        # Получаем новые действующие лимиты
        new_limits = await self.repository.get_limits(card_id=card.id)

        # Изменяем сведения о лимитах в API систем
        for system in card.systems:
            if system.short_name == 'ГПН':
                # Удаляем в ГПН текущие лимиты
                gpn_delete_card_limits.delay(
                    limit_ids=[limit.external_id for limit in limits_to_delete if limit.external_id]
                )

                # Создаем в ГПН новые лимиты
                gpn_create_card_limits.delay(
                    card_external_id=card.external_id,
                    limit_ids=[limit.id for limit in new_limits]
                )
                break

        return new_limits

    async def get_limits(self, card_id: str) -> List[CardLimitOrm]:
        limits = await self.repository.get_limits(card_id=card_id)
        return limits
