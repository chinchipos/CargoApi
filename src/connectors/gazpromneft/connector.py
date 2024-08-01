import hashlib
from datetime import datetime
from typing import Dict, Any, List

import requests
from fake_useragent import UserAgent
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import TZ
from src.connectors.gazpromneft.config import SYSTEM_SHORT_NAME, GPN_USERNAME, GPN_URL, GPN_TOKEN, GPN_PASSWORD
from src.connectors.irrelevant_balances import IrrelevantBalances
from src.database.model.card import CardOrm
from src.database.model.card_group import CardGroupOrm
from src.database.model.card_type import CardTypeOrm
from src.repositories.base import BaseRepository
from src.repositories.card import CardRepository
from src.repositories.system import SystemRepository
from src.utils.enums import ContractScheme
from src.utils.log import ColoredLogger
from src.database.model.models import CardSystem as CardSystemOrm

from sqlalchemy import select as sa_select


# print('-----------------------')
# print('Дамп запроса к API:')
# print(' ')
# data = dump.dump_all(response)
# print(data.decode('utf-8'))


class GPNConnector(BaseRepository):

    def __init__(self, session: AsyncSession, logger: ColoredLogger):
        super().__init__(session, None)
        self.logger = logger
        self.system = None
        self._irrelevant_balances = IrrelevantBalances()

        self.api_url = GPN_URL
        self.api_v1 = '/vip/v1'
        self.api_v2 = '/vip/v2'

        self.user_agent = UserAgent()
        api_key = GPN_TOKEN
        self.headers = {
            'user-agent': self.user_agent.random,
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'api_key': api_key
        }

        self.api_session_id = None
        self.contract_id = None
        self.auth_user()

        self.gpn_cards = []
        self.local_cards = []
        self.card_groups = []

    def endpoint(self, api_version: str, fn: str) -> str:
        return self.api_url + api_version + "/" + fn

    async def init_system(self) -> None:
        system_repository = SystemRepository(self.session)
        self.system = await system_repository.get_system_by_short_name(
            system_fhort_name=SYSTEM_SHORT_NAME,
            scheme=ContractScheme.OVERBOUGHT
        )

    async def sync(self) -> IrrelevantBalances:
        # Прогружаем наш баланс
        await self.load_balance()

        # Синхронизируем карты по номеру
        await self.sync_cards_by_number()

        # Прогружаем транзакции
        # await self.load_transactions(need_authorization=False)

        # Возвращаем объект со списком транзакций, начиная с которых требуется пересчитать балансы
        return self._irrelevant_balances

    def auth_user(self) -> None:
        """Авторизация пользователя"""

        username = GPN_USERNAME
        password = GPN_PASSWORD
        password_hash = hashlib.sha512(password.encode('utf-8')).hexdigest().lower()

        response = requests.post(
            url=self.endpoint(self.api_v1, "authUser"),
            headers=self.headers,
            data={
                "login": username,
                "password": password_hash
            }
        )

        resp_data = response.json()
        # print(resp_data)
        self.api_session_id = resp_data['data']['session_id']
        self.contract_id = resp_data['data']['contracts'][0]['id']

    def contract_info(self) -> Dict[str, Any]:
        """Получение информации об организации."""

        response = requests.get(
            url=self.endpoint(self.api_v1, "getPartContractData"),
            headers=self.headers | {"session_id": self.api_session_id},
            data={"contract_id": self.contract_id}
        )

        return response.json()

    async def load_balance(self) -> None:
        contract_data = self.contract_info()
        # print(contract_data)
        balance = float(contract_data['data']['balanceData']['available_amount'])
        self.logger.info('Наш баланс в системе {}: {} руб.'.format(self.system.full_name, balance))

        # Обновляем запись в локальной БД
        await self.update_object(self.system, update_data={
            "balance": balance,
            "balance_sync_dt": datetime.now(tz=TZ)
        })

    async def sync_cards_by_number(self) -> None:
        # Получаем список карт от системы
        gpn_cards = self.get_gpn_cards()

        # Получаем список карт из локальной БД
        local_cards = await self.get_local_cards()

        # Сравниваем карты локальные с полученными от поставщика.
        await self.compare_cards(gpn_cards, local_cards)

        # Записываем в БД время последней успешной синхронизации
        await self.update_object(self.system, update_data={"cards_sync_dt": datetime.now(tz=TZ)})
        self.logger.info('Синхронизация карт выполнена')

    def get_gpn_cards(self) -> List[Dict[str, Any]]:
        if not self.gpn_cards:
            response = requests.get(
                url=self.endpoint(self.api_v2, "cards"),
                headers=self.headers | {"session_id": self.api_session_id},
                data={"contract_id": self.contract_id}
            )
            resp_data = response.json()
            self.gpn_cards = resp_data["data"]["result"]

        return self.gpn_cards

    async def get_local_cards(self, card_numbers: List[str] | None = None) -> List[CardOrm]:
        if not self.local_cards:
            card_repository = CardRepository(self.session)
            self.local_cards = await card_repository.get_cards_by_numbers(card_numbers, self.system.id)

        return self.local_cards

    async def get_card_types(self, gpn_cards: List[Dict[str, Any]]) -> Dict[str, CardOrm]:
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

        local_card_types = {data.name: data for data in local_card_types_dataset}
        return local_card_types

    @staticmethod
    def get_equal_local_card(gpn_card: Dict[str, Any], local_cards: List[CardOrm]) -> CardOrm:
        i = 0
        length = len(local_cards)
        while i < length:
            if local_cards[i].card_number == gpn_card['number']:
                card = local_cards.pop(i)
                return card
            else:
                i += 1

    async def compare_cards(self, gpn_cards: List[Dict[str, Any]], local_cards: List[CardOrm]) -> None:
        """
        Сравниваем карты локальные с полученными от системы.
        Создаем в локальной БД карты, которые есть у системы, но нет локально.
        """
        # Типы карт, используемые в ГПН, должны присутствовать в локальной БД
        card_types = await self.get_card_types(gpn_cards)

        # Выгружаем из БД группы карт
        card_repository = CardRepository(self.session, None)
        await card_repository.get_card_groups()

        # Сравниваем карты из системы с локальными.
        # В локальной БД создаем новые, если появились в системе.
        # В локальной БД обновляем статус карт на тот, который установлен в системе.
        new_local_cards = []
        local_cards_to_update = []
        for gpn_card in gpn_cards:
            local_card = self.get_equal_local_card(gpn_card, local_cards)
            gpn_card_status_is_active = True if "locked" not in gpn_card["status"].lower() else False
            if local_card:
                # В локальной системе есть соответствующая карта - сверяем статусы и группы.
                # Группы в локальной БД имеют первичное значение.
                # Статусы в системе имеют первичное значение.
                changed = False
                if gpn_card_status_is_active != local_card:
                    local_card.is_active = gpn_card_status_is_active
                    changed = True

                local_card_ext_group_id = local_card.card_group.external_id if local_card.card_group_id else None
                if gpn_card['group_id'] != local_card_ext_group_id:
                    local_card_group = await card_repository.get_or_create_card_group(
                        gpn_card['group_id'], gpn_card['group_name'])
                    local_card.card_group_id = local_card_group.id if local_card_group else None
                    changed = True

                if changed:
                    local_cards_to_update.append(local_card)

            else:
                # В локальной системе нет такой карты - создаем её
                new_card_data = {
                    "card_number": gpn_card["number"],
                    "card_type_id": card_types[gpn_card["carrier_name"]].id,
                    "is_active": gpn_card_status_is_active,
                }
                new_card = await self.insert(CardOrm, **new_card_data)

                # Привязываем к системе
                card_system_date = {"card_id": new_card.id, "system_id": self.system.id}
                await self.insert(CardSystemOrm, **card_system_date)

                # Присваиваем группу
                card_group = await self.get_or_create_card_group(gpn_card['group_id'], gpn_card['group_name'])
                new_card.card_group_id = card_group.id if card_group else None

                new_local_cards.append(new_card)

        # Обновляем в БД карты
        if local_cards_to_update:
            local_cards_to_update = [
                {
                    "id": card.id,
                    "is_active": card.is_active,
                    "card_group_id": card.card_group_id,
                } for card in local_cards_to_update
            ]
            await self.bulk_update(CardOrm, local_cards_to_update)

        if new_local_cards:
            self.logger.info(f"Импортировано {len(new_local_cards)} новых карт")
