import hashlib
import json
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, List

import requests
from fake_useragent import UserAgent

from src.celery_app.exceptions import CeleryError
from src.celery_app.gpn.config import GPN_USERNAME, GPN_URL, GPN_TOKEN, GPN_PASSWORD
from src.config import PRODUCTION, TZ
from src.utils.loggers import get_logger


class ProductCategory(Enum):
    FOOD = {"id": "1-C8J1M", "code": "40100000000", "unit": "IT"}
    CAFE = {"id": "1-C8J1I", "code": "40200000000", "unit": "IT"}
    NON_FOOD = {"id": "1-C8J1Z", "code": "40300000000", "unit": "IT"}
    OTHER_SERVICES = {"id": "1-C8J2B", "code": "40400000000", "unit": "IT"}
    CS_SERVICES = {"id": "1-4SE0LKU", "code": "CS_SERVICES", "unit": "IT"}
    FUEL = {"id": "1-CK231", "code": "FUEL", "unit": "LIT"}

    @staticmethod
    def not_fuel_categories():
        return [
            ProductCategory.FOOD,
            ProductCategory.CAFE,
            ProductCategory.NON_FOOD,
            ProductCategory.OTHER_SERVICES,
            ProductCategory.CS_SERVICES
        ]


class GPNApi:

    def __init__(self):
        self.logger = get_logger(name="GPNApi", filename="celery.log")
        self.today = datetime.now(tz=TZ).date()

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

        self.product_types = None

    def endpoint(self, api_version: str, fn: str, params: Dict[str, Any] | None = None) -> str:
        url = self.api_url + api_version + "/" + fn
        if params:
            url += "?" + "&".join([f"{key}={value}" for key, value in params.items()])
        return url

    def auth_user(self) -> None:
        """Авторизация пользователя"""

        password_hash = hashlib.sha512(GPN_PASSWORD.encode('utf-8')).hexdigest().lower()

        data = {
            "login": GPN_USERNAME,
            "password": password_hash
        }
        response = requests.post(
            url=self.endpoint(self.api_v1, "authUser"),
            headers=self.headers,
            data=data
        )
        try:
            res = response.json()
        except Exception as e:
            self.logger.info(response.text)
            self.logger.exception(e)
            raise CeleryError(message="Ошибка авторизации", trace=False)

        if res["status"]["code"] != 200:
            raise CeleryError(message=f"Ошибка авторизации. Ответ API: {res['status']['errors']}. "
                                      f"Наш запрос: {data}")

        self.api_session_id = res['data']['session_id']
        self.contract_id = res['data']['contracts'][0]['id']

    def contract_info(self) -> Dict[str, Any]:
        """Получение информации об организации."""

        response = requests.get(
            url=self.endpoint(self.api_v1, "getPartContractData", params={"contract_id": self.contract_id}),
            headers=self.headers | {"session_id": self.api_session_id}
        )

        res = response.json()
        if res["status"]["code"] != 200:
            raise CeleryError(message=f"Ошибка при получении информации о договоре. "
                                      f"Ответ API: {res['status']['errors']}.")

        return res["data"]

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
        self.logger.info("Пауза 40 сек")
        time.sleep(40)
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
        if res['status']['code'] != 200:
            raise CeleryError(
                message=f"Не удалось удалить группу карт в ГПН | ID: {group_id} | NAME: {group_name}"
            )

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
            self.logger.info('Пауза 40 сек')
            time.sleep(40)

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
            if res['status']['code'] != 200:
                raise CeleryError(
                    message=f"Не удалось открепить карту от группы. "
                            f"Ответ API ГПН: {res['status']['errors']}. Наш запрос: {data}"
                )

            self.logger.info(f"Карты {[card['id'] for card in cards]} откреплены от группы {group_id}")
            self.logger.info("Пауза 40 сек")
            time.sleep(40)

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

    def get_transactions(self, transaction_days: int) -> List[Dict[str, Any]]:
        # Цитата из документации на API:
        # Разница между значениями параметров «date_from» и «date_to» должна быть не больше месяца
        # (рассчитывается от количества дней в месяце, указанном в параметре «date_from»)
        _transaction_days = transaction_days if 0 < transaction_days <= 28 else 28
        date_from = self.today - timedelta(days=_transaction_days)

        # Цитата из документации на API:
        # Количество транзакций на странице. 500, если не указано.
        page_offset = 0
        transactions = []
        i = 0
        while True:
            params = {
                "date_from": date_from.isoformat(),
                "date_to": self.today.isoformat(),
                "page_limit": 100,
                "page_offset": page_offset
            }
            url = self.endpoint(self.api_v2, "transactions", params)
            response = requests.get(
                url=url,
                headers=self.headers | {"session_id": self.api_session_id}
            )

            res = response.json()

            if res["status"]["code"] != 200:
                raise CeleryError(message=f"Ошибка при получении транзакций. Ответ сервера API: "
                                          f"{res['status']['errors']}. Наш запрос: {params}")
            # print(url)
            print(response.text)
            if not res["data"]["total_count"]:
                self.logger.info(f"В системе ГПН отсутствуют транзакции за за указанный период {_transaction_days} дн")
                break

            transactions.extend(res["data"]["result"])
            # print('----------------------')
            # print(f'OFFSET: {page_offset}')
            # print(res["data"]["result"])
            page_offset += 100
            i += 1
            if i == 3:
                break

        for transaction in transactions:
            transaction['timestamp'] = datetime.fromisoformat(transaction['timestamp'][:19])

        return transactions

    def set_group_limit(self, limit_id: str | None, group_id: str, product_category: ProductCategory, limit_sum: int) \
            -> None:
        new_limit = {
            "contract_id": self.contract_id,
            "group_id": group_id,
            "productType": product_category.value["id"],
            "sum": {
                "currency": "810",
                "value": int(limit_sum)
            },
            "term": {"type": 1},
            "time": {"number": 1, "type": 2}
        }
        # Если задан параметр limit_id, то будет изменен существующий лимит.
        # Если не задан, то будет создан новый.
        if limit_id:
            new_limit['id'] = limit_id

        data = {"limit": json.dumps([new_limit])}
        response = requests.post(
            url=self.endpoint(self.api_v1, "setLimit"),
            headers=self.headers | {"session_id": self.api_session_id},
            data=data
        )
        res = response.json()

        if res["status"]["code"] != 200:
            raise CeleryError(message=f"Ошибка при установке лимита. Ответ сервера API: "
                                      f"{res['status']['errors']}. Наш запрос: {data}")

        self.logger.info(f"Установлен лимит {new_limit}")
        """
        new_limits = []

        # Получаем все возможные категории продуктов
        product_types = self.get_product_types()

        # Получаем от ГПН список всех групп
        if not groups:
            groups = self.get_card_groups()

        for limit_data in limits_dataset:
            personal_account = limit_data[0]
            limit_value = limit_data[1]

            if limit_value < 1:
                limit_value = 1

            # По ЛС организации определяем ID группы
            group_id = None
            for group in groups:
                if group['name'] == personal_account:
                    group_id = group['id']
                    break

            if not group_id:
                group_id = self.create_card_group(personal_account)

            # Запрашиваем список установленных на группу товарных лимитов
            limits = self.get_card_group_limits(group_id)

            # Проверяем по всем ли категориям продуктов установлен лимит для заданной группы карт
            for product_type in product_types:
                limit_id = None
                for limit in limits:
                    if limit['productType'] == product_type['id']:
                        # Изменяем лимит на эту категорию товаров для этой группы
                        limit_id = limit['id']
                        break

                new_limits.append(
                    self.make_card_group_limit_data(
                        limit_id=limit_id,
                        group_id=group_id,
                        product_type_id=product_type['id'],
                        limit_value=limit_value)
                )

        # Устанавливаем новые лимиты
        for new_limit in new_limits:
            time.sleep(0.5)
            data = {"limit": json.dumps([new_limit])}
            response = requests.post(
                url=self.endpoint(self.api_v1, "setLimit"),
                headers=self.headers | {"session_id": self.api_session_id},
                data=data
            )
            res = response.json()

            if res["status"]["code"] != 200:
                raise CeleryError(message=f"Ошибка при установке лимитов. Ответ сервера API: "
                                          f"{res['status']['errors']}. Наш запрос: {data}")

            self.logger.info(f"Установлен лимит {new_limit}")
        """

    def delete_group_limit(self, limit_id: str, group_id: str) -> None:
        data = {
            "contract_id": self.contract_id,
            "limit_id": limit_id,
            "group_id": group_id,
        }
        response = requests.post(
            url=self.endpoint(self.api_v1, "removeLimit"),
            headers=self.headers | {"session_id": self.api_session_id},
            data=data
        )
        res = response.json()

        if res["status"]["code"] != 200:
            raise CeleryError(message=f"Ошибка при удалении лимита. Ответ сервера API: "
                                      f"{res['status']['errors']}. Наш запрос: {data}")

        self.logger.info(f"Удален лимит {data}")

    def get_card_group_limits(self, group_id: str) -> List[Dict[str, Any]]:
        """
        Лимиты можно получить либо по договору, либо по группе карт, либо по карте.
        Нет возможности получить все лимиты одним запросом.
        """
        params = {
            "contract_id": self.contract_id,
            "group_id": group_id,
        }
        response = requests.get(
            url=self.endpoint(self.api_v1, "limit", params),
            headers=self.headers | {"session_id": self.api_session_id}
        )
        res = response.json()

        if res["status"]["code"] != 200:
            raise CeleryError(message=f"Ошибка при получении установленных на группу лимитов. Ответ сервера API: "
                                      f"{res['status']['errors']}. Наш запрос: {params}")

        limits = res["data"]["result"]
        return limits

    def get_product_types(self) -> List[Dict[str, Any]]:
        if not self.product_types:
            self.product_types = self.get_dictionary(dictionary_name="ProductType")

        return self.product_types

    def get_goods(self) -> List[Dict[str, Any]]:
        goods = self.get_dictionary(dictionary_name="Goods")
        # print(goods)
        return goods

    def get_dictionary(self, dictionary_name: str) -> List[Dict[str, Any]]:
        response = requests.get(
            url=self.endpoint(self.api_v1, "getDictionary", params={"name": dictionary_name}),
            headers=self.headers | {"session_id": self.api_session_id}
        )
        res = response.json()

        if res["status"]["code"] != 200:
            raise CeleryError(message=f"Ошибка при получении справочника {dictionary_name}. Ответ сервера API: "
                                      f"{res['status']['errors']}.")

        return res["data"]["result"]

    def issue_virtual_card(self) -> Dict[str, Any]:
        data = {
            "contract_id": self.contract_id,
            "type": "limit"
        }
        response = requests.post(
            url=self.endpoint(self.api_v2, "cards/release"),
            headers=self.headers | {"session_id": self.api_session_id},
            data=data
        )
        res = response.json()
        if res["status"]["code"] != 200:
            raise CeleryError(message=f"Ошибка при выпуске виртуальной карты ГПН. "
                                      f"Ответ API: {res['status']['errors']}. Наш запрос: {data}")

        card = res['data']
        self.logger.info(f"{card['number']} | в ГПН создана виртуальная карта")
        time.sleep(0.4)
        return card
