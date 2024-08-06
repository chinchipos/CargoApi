from datetime import datetime
import time
from typing import Dict, Any, List

from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.celery.gpn.api import GPNApi
from src.celery.gpn.config import SYSTEM_SHORT_NAME
from src.celery.irrelevant_balances import IrrelevantBalances
from src.config import TZ
from src.database.model.card import CardOrm, BlockingCardReason
from src.database.model.card_type import CardTypeOrm
from src.database.model.models import CardSystem as CardSystemOrm, Balance as BalanceOrm
from src.repositories.base import BaseRepository
from src.repositories.card import CardRepository
from src.repositories.system import SystemRepository
from src.utils.enums import ContractScheme
from src.utils.log import ColoredLogger


class GPNController(BaseRepository):

    def __init__(self, session: AsyncSession, logger: ColoredLogger):
        super().__init__(session, None)
        self.logger = logger
        self.api = GPNApi(logger)
        self.system = None
        self._irrelevant_balances = IrrelevantBalances()
        self.card_groups = []
        self.card_types = {}

    async def init_system(self) -> None:
        if not self.system:
            system_repository = SystemRepository(self.session)
            self.system = await system_repository.get_system_by_short_name(
                system_fhort_name=SYSTEM_SHORT_NAME,
                scheme=ContractScheme.OVERBOUGHT
            )

    async def sync(self) -> IrrelevantBalances:
        await self.init_system()

        # Прогружаем наш баланс
        await self.load_balance()

        # Синхронизируем карты по номеру
        # await self.sync_cards()

        # Прогружаем транзакции
        # await self.load_transactions(need_authorization=False)

        # Возвращаем объект со списком транзакций, начиная с которых требуется пересчитать балансы
        return self._irrelevant_balances

    async def load_balance(self) -> None:
        contract_data = self.api.contract_info()
        balance = float(contract_data['data']['balanceData']['available_amount'])
        self.logger.info('Наш баланс в системе {}: {} руб.'.format(self.system.full_name, balance))

        # Обновляем запись в локальной БД
        await self.update_object(self.system, update_data={
            "balance": balance,
            "balance_sync_dt": datetime.now(tz=TZ)
        })

    async def sync_cards(self) -> None:
        await self.init_system()

        # Получаем список карт от системы
        remote_cards = self.api.get_gpn_cards()
        self.logger.info(f"Количество карт в API ГПН: {len(remote_cards)}")

        # Получаем типы карт
        await self.get_card_types(remote_cards)

        # Получаем список карт из локальной БД, привязанных к ГПН
        local_cards = await self.get_local_cards()
        self.logger.info(f"Количество карт в локальной БД (до синхронизации): {len(local_cards)}")

        # Создаем в локальной БД новые карты и привязываем их к ГПН - статус карты из ГПН транслируем на локальную БД.
        # Привязываем в локальной БД карты, открепленные от ГПН - статус не устанавливаем.
        # created_or_updated = False
        local_card_numbers = [local_card.card_number for local_card in local_cards]
        for remote_card in remote_cards:
            if remote_card['number'] not in local_card_numbers:
                is_active = True if "locked" not in remote_card["status"].lower() else False
                await self.process_unbinded_local_card_or_create_new(
                    external_id=remote_card['id'],
                    card_number=remote_card['number'],
                    card_type_name=remote_card["carrier_name"],
                    is_active=is_active
                )
                # created_or_updated = True

        # Локальным картам присваиваем external_id, если не присвоено
        dataset = []
        for local_card in local_cards:
            for remote_card in remote_cards:
                if remote_card['number'] == local_card.card_number:
                    if remote_card['id'] != local_card.external_id:
                        dataset.append({"id": local_card.id, "external_id": remote_card['id']})

        if dataset:
            await self.bulk_update(CardOrm, dataset)

        """
        # Синхронизируем сами группы карт
        await self.sync_card_groups()

        # Получаем список карт из локальной БД, привязанных к ГПН
        if created_or_updated:
            local_cards = await self.get_local_cards()
            self.logger.info(f"Количество карт в локальной БД (после синхронизации): {len(local_cards)}")

        # Из API получаем список групп карт
        gpn_card_groups = self.api.get_card_groups()
        print("Группы карт ГПН:")
        for gpn_group in gpn_card_groups:
            print(gpn_group)
        gpn_group_id_by_name = {gpn_card_group['name']: gpn_card_group['id'] for gpn_card_group in gpn_card_groups}

        # Сравниваем группы карт, присвоенные картам. Записи в локальной БД имеют первичное значение.
        gpn_cards_dict = {card['number']: card for card in remote_cards}
        for local_card in local_cards:
            gpn_card = gpn_cards_dict[local_card.card_number]
            if gpn_card['group_id'] != local_card.group_id:
                if local_card.company_id:
                    self.api.bind_cards_to_group(
                        card_id=gpn_card['id'],
                        group_id=gpn_group_id_by_name[local_card.company.personal_account]
                    )
                else:
                    self.api.unbind_cards_from_group(gpn_card_id=gpn_card['id'])

        # Записываем в БД время последней успешной синхронизации
        await self.update_object(self.system, update_data={"cards_sync_dt": datetime.now(tz=TZ)})
        self.logger.info('Синхронизация карт выполнена')
    """

    async def get_local_cards(self) -> List[CardOrm]:
        card_repository = CardRepository(self.session)
        local_cards = await card_repository.get_cards_by_filters(system_id=self.system.id)

        return local_cards

    async def get_card_types(self, gpn_cards: List[Dict[str, Any]]) -> None:
        """
        Получаем из локальной БД список типов карт, соответствующих типам карт в ГПН.
        Если в локальной БД не найдено, то создаем новые типы.
        """
        gpn_card_type_names = [card["carrier_name"] for card in gpn_cards]
        stmt = sa_select(CardTypeOrm).where(CardTypeOrm.name.in_(gpn_card_type_names))
        local_card_types_dataset = await self.select_all(stmt)

        if len(gpn_card_type_names) != len(local_card_types_dataset):
            local_card_type_names = [ct.name for ct in local_card_types_dataset]
            new_card_types = []
            for gpn_card_type_name in gpn_card_type_names:
                if gpn_card_type_name not in local_card_type_names:
                    new_card_types.append({"name": gpn_card_type_name})

            await self.bulk_insert_or_update(CardTypeOrm, new_card_types, index_field="name")

            stmt = sa_select(CardTypeOrm).where(CardTypeOrm.name.in_(gpn_card_type_names))
            local_card_types_dataset = await self.select_all(stmt)

        self.card_types = {data.name: data for data in local_card_types_dataset}

    """
    async def sync_card_groups(self):
        # Из локальной БД получаем список лицевых счетов организаций, которым присвоены карты ГПН.
        # Лицевые счета являются наименованиями для групп карт
        stmt = (
            sa_select(CompanyOrm)
            .select_from(CompanyOrm, CardOrm, CardSystemOrm)
            .where(CompanyOrm.id == CardOrm.company_id)
            .where(CardOrm.id == CardSystemOrm.card_id)
            .where(CardSystemOrm.system_id == self.system.id)
        )
        companies = await self.select_all(stmt)
        # personal_accounts = [company.personal_account for company in companies]

        # Из API получаем список групп карт
        gpn_groups = self.api.get_card_groups()

        # Сравниваем непосредственно группы карт.
        # Совпадающие записи убираем из списков для уменьшения стоимости алгоритмя поиска.
        i = 0
        while i < len(companies):
            company = companies[i].personal_account
            found = False
            for gpn_group in gpn_groups:
                if gpn_group['name'] == company.personal_account:
                    found = True
                    companies[i].remove(company)
                    gpn_groups.remove(gpn_group)
                    break

            if not found:
                i += 1

        # Удаляем в API избыточные группы.
        for group in gpn_groups:
            self.api.delete_gpn_group(group_id=group['id'], group_name=group['name'])

        # Создаем в API недостающие группы.
        for company in companies:
            self.api.create_card_group(group_name=company.personal_account)
    """

    async def process_unbinded_local_card_or_create_new(self, external_id: str, card_number: str, card_type_name: str,
                                                        is_active: bool) -> None:
        stmt = sa_select(CardOrm).where(CardOrm.card_number == card_number)
        card = await self.select_first(stmt)
        if card:
            # Карта существует, но она не привязана к ГПН. Привязываем её.
            card_system_date = {"card_id": card.id, "system_id": self.system.id}
            await self.insert(CardSystemOrm, **card_system_date)

            self.logger.info(f"{card_number} | существующая в БД карта привязана к ГПН")

        else:
            # Карта не существует в локальной БД. Создаем её.
            new_card_data = {
                "external_id": external_id,
                "card_number": card_number,
                "card_type_id": self.card_types[card_type_name].id,
                "is_active": is_active,
            }
            new_card = await self.insert(CardOrm, **new_card_data)

            # Привязываем к системе
            card_system_date = {"card_id": new_card.id, "system_id": self.system.id}
            await self.insert(CardSystemOrm, **card_system_date)

            self.logger.info(f"{card_number} | в БД создана новая карта и привязана к ГПН")

    async def gpn_bind_company_to_cards(self, card_ids: List[str], personal_account: str, limit_sum: int | float) \
            -> None:
        await self.init_system()

        # Получаем из ГПН группу с наименованием, содержащим personal account
        # Если нет такой, то создаем.
        group_id = None
        # Из API получаем список групп карт
        groups = self.api.get_card_groups()
        for group in groups:
            if group['name'] == personal_account:
                group_id = group['id']
                break

        if not group_id:
            group_id = self.api.create_card_group(personal_account)
            self.logger.info("Пауза 40 сек")
            time.sleep(40)
            self.api.set_card_group_limits([(personal_account, limit_sum)])

        # Привязываем карту к группе в API ГПН
        stmt = sa_select(CardOrm).where(CardOrm.id.in_(card_ids)).order_by(CardOrm.card_number)
        cards = await self.select_all(stmt)
        card_external_ids = [card.external_id for card in cards]
        self.api.bind_cards_to_group(card_external_ids=card_external_ids, group_id=group_id)

        # Привязываем карты к группе в локальной БД
        dataset = [
            {
                "id": card.id,
                "group_id": group_id
            } for card in cards
        ]
        await self.bulk_update(CardOrm, dataset)

    async def gpn_unbind_company_from_cards(self, card_ids: List[str]) -> None:
        await self.init_system()

        stmt = sa_select(CardOrm).where(CardOrm.id.in_(card_ids)).order_by(CardOrm.card_number)
        cards = await self.select_all(stmt)
        card_external_ids = [card.external_id for card in cards]

        # Отвязываем карту от группы в API ГПН
        self.api.unbind_cards_from_group(card_external_ids=card_external_ids)

        # Устанавливаем статус карты в API ГПН
        self.api.block_cards(card_external_ids)

    async def set_card_states(self, balance_ids_to_change_card_states: Dict[str, List[str]]):
        # В функцию переданы ID балансов, картам которых нужно сменить состояние (заблокировать или разблокировать).
        # Меняем статус в локальной БД, потом устанавливаем новый статус в системе поставщика.
        await self.init_system()

        # Получаем карты из локальной БД
        card_repository = CardRepository(self.session, None)
        local_cards_to_activate = await card_repository.get_cards_by_filters(
            balance_ids=balance_ids_to_change_card_states["to_activate"],
            system_id=self.system.id
        )
        local_cards_to_activate = [card for card in local_cards_to_activate
                                   if not card.is_active and card.reason_for_blocking != BlockingCardReason.PIN]
        local_cards_to_block = await card_repository.get_cards_by_filters(
            balance_ids=balance_ids_to_change_card_states["to_block"],
            system_id=self.system.id
        )
        local_cards_to_block = [card for card in local_cards_to_block if card.is_active]

        # Обновляем состояние карт в локальной БД
        if local_cards_to_activate or local_cards_to_block:
            dataset = [
                {
                    "id": card.id,
                    "is_active": True,
                    "reason_for_blocking": None
                } for card in local_cards_to_activate
            ]
            dataset.extend([
                {
                    "id": card.id,
                    "is_active": False,
                    "reason_for_blocking": BlockingCardReason.NNK
                } for card in local_cards_to_block
            ])
            await self.bulk_update(CardOrm, dataset)

        # Устанавливаем статусы карт в системе поставщика
        if local_cards_to_activate:
            ext_card_ids = [card.external_id for card in local_cards_to_activate]
            self.api.activate_cards(ext_card_ids)

        if local_cards_to_block:
            ext_card_ids = [card.external_id for card in local_cards_to_block]
            self.api.block_cards(ext_card_ids)

    async def set_card_group_limit(self, balance_id: str) -> None:
        # Получаем параметры баланса и организации
        stmt = (
            sa_select(BalanceOrm)
            .options(
                joinedload(BalanceOrm.company)
            )
            .where(BalanceOrm.id == balance_id)
        )
        balance = await self.select_first(stmt)

        # Вычисляем доступный лимит
        overdraft_sum = balance.company.overdraft_sum if balance.company.overdraft_on else 0
        boundary_sum = balance.company.min_balance - overdraft_sum
        limit_sum = abs(boundary_sum - balance.balance) if boundary_sum < balance.balance else 1

        # Устанавливаем лимит
        gpn_api = GPNApi(self.logger)
        gpn_api.set_card_group_limits(limits_dataset=[(balance.company.personal_account, limit_sum)])
