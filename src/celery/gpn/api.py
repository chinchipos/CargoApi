import hashlib
import json
import time
from typing import Dict, Any, List

import requests
from fake_useragent import UserAgent

from src.celery.exceptions import CeleryError
from src.celery.gpn.config import GPN_USERNAME, GPN_URL, GPN_TOKEN, GPN_PASSWORD
from src.config import PRODUCTION
from src.utils.log import ColoredLogger


class GPNApi:

    def __init__(self, logger: ColoredLogger):
        self.logger = logger

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

    def endpoint(self, api_version: str, fn: str, params: Dict[str, Any] | None = None) -> str:
        url = self.api_url + api_version + "/" + fn
        if params:
            url += "?" + "&".join([f"{key}={value}" for key, value in params.items()])
        return url

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
        self.api_session_id = resp_data['data']['session_id']
        self.contract_id = resp_data['data']['contracts'][0]['id']

    def contract_info(self) -> Dict[str, Any]:
        """Получение информации об организации."""

        response = requests.get(
            url=self.endpoint(self.api_v1, "getPartContractData", params={"contract_id": self.contract_id}),
            headers=self.headers | {"session_id": self.api_session_id}
        )

        return response.json()

    def get_card_groups(self) -> List[Dict[str, Any]]:
        response = requests.get(
            url=self.endpoint(self.api_v1, "cardGroups", params={"contract_id": self.contract_id}),
            headers=self.headers | {"session_id": self.api_session_id}
        )
        groups = response.json()['data']['result']
        return groups

    def create_card_group(self, group_name: str) -> str:
        # Создаем группу в API
        new_group_name = group_name
        data = {
            "contract_id": self.contract_id,
            "name": new_group_name
        }
        response = requests.post(
            url=self.endpoint(self.api_v1, "setCardGroup"),
            headers=self.headers | {"session_id": self.api_session_id},
            data=data
        )
        res = response.json()
        if res["status"]["code"] != 200:
            raise CeleryError(message=f"Ошибка при создании группы карт ГПН. Ответ API: {res['status']['errors']}. "
                                      f"Наш запрос: {data}")

        gpn_group_id = res['data']['id']
        self.logger.info(f"{new_group_name} | в ГПН создана группа карт")
        return gpn_group_id

    def delete_gpn_group(self, group_id: str, group_name: str) -> None:
        # Удаляем группу в API
        response = requests.post(
            url=self.endpoint(self.api_v1, "removeCardGroup"),
            headers=self.headers | {"session_id": self.api_session_id},
            data={
                "contract_id": self.contract_id,
                "group_id": group_id
            }
        )
        res = response.json()
        if not res['data']:
            raise CeleryError(message=f"Не удалось удалить группу карт в ГПН | ID: {group_id} | NAME: {group_name}")
        else:
            self.logger.info(f"В ГПН удалена группа карт | ID: {group_id} | NAME: {group_name}")

    def bind_cards_to_group(self, card_external_ids: List[str], group_id: str) -> None:
        # Получаем список карт ГПН.
        # Если картам уже назначена эта группа, то ничего с ней не делаем.
        # Если картам назначена другая группа, то открепляем карту от группы.
        remote_cards = self.get_gpn_cards()
        remote_cards_to_unbind_group = [
            card for card in remote_cards
            if card['id'] in card_external_ids and card['group_id'] and card['group_id'] != group_id
        ]

        if remote_cards:
            external_ids = [card['id'] for card in remote_cards_to_unbind_group]
            self.unbind_cards_from_group(external_ids, remote_cards_to_unbind_group)
            print('Пауза 60 сек')
            time.sleep(60)

        card_external_ids_to_bind_group = [
            card['id'] for card in remote_cards
            if card['id'] in card_external_ids and card['group_id'] != group_id
        ]

        cards_list = [{"id": card_ext_id, "type": "Attach"} for card_ext_id in card_external_ids_to_bind_group]
        data = {
            "contract_id": self.contract_id,
            "group_id": group_id,
            "cards_list": json.dumps(cards_list)
        }
        response = requests.post(
            url=self.endpoint(self.api_v1, "setCardsToGroup"),
            headers=self.headers | {"session_id": self.api_session_id},
            data=data
        )
        res = response.json()
        if res['status']['code'] == 200:
            self.logger.info(f"Прикреплены карты {card_external_ids_to_bind_group} к группе {group_id}")
        else:
            raise CeleryError(
                message=f"Не удалось включить карту в группу. "
                        f"Ответ API ГПН: {res['status']['errors']}. Наш запрос: {data}"
            )

    def unbind_cards_from_group(self, card_external_ids: List[str], remote_cards: List[Dict[str, Any]] | None = None) \
            -> None:
        if not card_external_ids:
            return None

        # Получаем список карт ГПН
        if not remote_cards:
            remote_cards = self.get_gpn_cards()

        remote_cards = {card['id']: card for card in remote_cards if card['id'] in card_external_ids}

        # Группируем карты по идентификатору группы
        grouped_cards = {}
        for card_external_id in card_external_ids:
            if card_external_id in remote_cards:
                card = remote_cards[card_external_id]
                group_id = card['group_id']
                if group_id:
                    if group_id in grouped_cards:
                        grouped_cards[group_id].append(card)
                    else:
                        grouped_cards[group_id] = [card]
        for group_id, cards in grouped_cards.items():
            # открепляем карты от группы
            cards_list = [{"id": card['id'], "type": "Detach"} for card in cards]
            data = {
                "contract_id": self.contract_id,
                "group_id": group_id,
                "cards_list": json.dumps(cards_list)
            }
            response = requests.post(
                url=self.endpoint(self.api_v1, "setCardsToGroup"),
                headers=self.headers | {"session_id": self.api_session_id},
                data=data
            )
            res = response.json()
            if res['status']['code'] == 200:
                self.logger.info(f"Откреплены карты {[card['id'] for card in cards]} от группы {group_id}")
            else:
                raise CeleryError(
                    message=f"Не удалось открепить карту от группы. "
                            f"Ответ API ГПН: {res['status']['errors']}. Наш запрос: {data}"
                )

    def get_gpn_cards(self) -> List[Dict[str, Any]]:
        response = requests.get(
            url=self.endpoint(self.api_v2, "cards", params={"contract_id": self.contract_id}),
            headers=self.headers | {"session_id": self.api_session_id}
        )
        resp_data = response.json()
        gpn_cards = resp_data["data"]["result"]

        return gpn_cards

    def block_cards(self, external_card_ids: List[str]) -> None:
        self.set_cards_state(external_card_ids, block=True)

    def activate_cards(self, external_card_ids: List[str]) -> None:
        self.set_cards_state(external_card_ids, block=False)

    def set_cards_state(self, external_card_ids: List[str], block: bool) -> None:
        if not PRODUCTION:
            action = "Псевдоблокировка" if block else "Псевдоразблокировка"
            for external_card_id in external_card_ids:
                self.logger.info(f"{action} карты в ННК | {external_card_id}")
        else:
            data = {
                "contract_id": self.contract_id,
                "card_id": json.dumps(external_card_ids),
                "block": "true" if block else "false"
            }
            response = requests.post(
                url=self.endpoint(self.api_v1, "blockCard"),
                headers=self.headers | {"session_id": self.api_session_id},
                data=data
            )
            res = response.json()
            if 'errors' in res['status']:
                action = "заблокировать" if block else "разблокировать"
                raise CeleryError(message=f"Не удалось {action} карты в системе ГПН. Ответ API: "
                                          f"{res['status']['errors']}. Наш запрос: {data}")

    def gpn_test(self) -> None:
        """
        groups = self.get_gpn_groups()
        for group in groups:
            print(group)
        """
        """
        print("Запрашиваю список установленных на группу товарных ограничителей")
        params = {
            "contract_id": self.contract_id,
            "group_id": "1-16XSTOLI",
        }
        response = requests.get(
            url=self.endpoint(self.api_v1, "restriction", params),
            headers=self.headers | {"session_id": self.api_session_id}
        )
        res = response.json()
        restrictions = res["data"]["result"]
        if not restrictions:
            print("Товарные ограничители не установлены")
        for restriction in restrictions:
            print(restriction)

        print("Запрашиваю список установленных на группу товарных лимитов")
        params = {
            "contract_id": self.contract_id,
            "group_id": "1-16XSTOLI",
        }
        response = requests.get(
            url=self.endpoint(self.api_v1, "limit", params),
            headers=self.headers | {"session_id": self.api_session_id}
        )
        res = response.json()
        limits = res["data"]["result"]
        if not limits:
            print("Товарные лимиты не установлены")
        for limit in limits:
            print('---')
            print(limit)
        """
        """
        print("Запрашиваю справочник типов продукта")
        params = {
            "name": "ProductType",
        }
        response = requests.get(
            url=self.endpoint(self.api_v1, "getDictionary", params),
            headers=self.headers | {"session_id": self.api_session_id}
        )
        res = response.json()
        product_types = res["data"]["result"]
        for product_type in product_types:
            print('---')
            print(product_type)

        print('---')
        """

        print("Попытка установить товарный лимит на группу карт без указания категории товаров")
        data = {
            "limit": json.dumps([{
                "contract_id": self.contract_id,
                "group_id": "1-16XSTOLI",
                "productType": "",
                "sum": {
                    "currency": "810",
                    "value": 333333
                },
                "term": {"type": 1},
                "time": {"number": 3, "type": 7}
            }])
        }
        response = requests.post(
            url=self.endpoint(self.api_v1, "setLimit"),
            headers=self.headers | {"session_id": self.api_session_id},
            data=data
        )
        res = response.json()
        print(res)
