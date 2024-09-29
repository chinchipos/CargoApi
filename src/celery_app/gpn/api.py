import hashlib
import json
import time
from datetime import datetime, timedelta, date
from enum import Enum
from typing import Dict, Any, List

import requests
from fake_useragent import UserAgent

from src.celery_app.exceptions import CeleryError
from src.config import GPN_USERNAME, GPN_URL, GPN_TOKEN, GPN_PASSWORD
from src.config import TZ
from src.database.models.goods_category import GoodsCategory
from src.database.models.limit import Unit, LimitPeriod
from src.utils.loggers import get_logger


class GpnGoodsCategory(Enum):
    __order__ = 'FUEL OTHER_SERVICES CAFE FOOD NON_FOOD CS_SERVICES'
    FUEL = {"id": "1-CK231", "code": "FUEL", "unit": "LIT", "local_category": GoodsCategory.FUEL}
    OTHER_SERVICES = {"id": "1-C8J2B", "code": "40400000000", "unit": "IT",
                      "local_category": GoodsCategory.OTHER_SERVICES}
    CAFE = {"id": "1-C8J1I", "code": "40200000000", "unit": "IT", "local_category": GoodsCategory.CAFE}
    FOOD = {"id": "1-C8J1M", "code": "40100000000", "unit": "IT", "local_category": GoodsCategory.FOOD}
    NON_FOOD = {"id": "1-C8J1Z", "code": "40300000000", "unit": "IT", "local_category": GoodsCategory.NON_FOOD}
    CS_SERVICES = {"id": "1-4SE0LKU", "code": "CS_SERVICES", "unit": "IT", "local_category": GoodsCategory.ROAD_PAYING}

    @staticmethod
    def not_fuel_categories():
        return [
            GpnGoodsCategory.FOOD,
            GpnGoodsCategory.CAFE,
            GpnGoodsCategory.NON_FOOD,
            GpnGoodsCategory.OTHER_SERVICES,
            GpnGoodsCategory.CS_SERVICES
        ]

    @staticmethod
    def get_equal_by_local(local_category: GoodsCategory):
        for gpn_category in GpnGoodsCategory:
            print('PPPPPPPPPPPPPPPPPPPPPP')
            print(gpn_category.value["local_category"].name)
            print(local_category.name)
            print(gpn_category.value["local_category"].name == local_category.name)
            if gpn_category.value["local_category"].name == local_category.name:
                return gpn_category


class GPNApi:

    def __init__(self):
        self.logger = get_logger(name="GPNApi", filename="celery.log")
        self.today: date = datetime.now(tz=TZ).date()

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
        data = {
            "contract_id": self.contract_id,
            "name": group_name
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
        self.logger.info(f"В ГПН создана группа карт {group_name}")
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

    def bind_cards_to_group(self, card_numbers: List[str], card_external_ids: List[str], group_id: str) -> None:
        # Получаем список карт ГПН.
        # Если картам уже назначена эта группа, то ничего с ней не делаем.
        # Если картам назначена другая группа, то открепляем карту от группы.
        remote_cards = self.get_gpn_cards()
        remote_cards_to_unbind_group = [
            card for card in remote_cards
            if card['id'] in card_external_ids and card['group_id'] and card['group_id'] != group_id
        ]

        if remote_cards_to_unbind_group:
            external_ids = [card['id'] for card in remote_cards_to_unbind_group]
            self.unbind_cards_from_group(
                card_numbers=card_numbers,
                card_external_ids=external_ids,
                group_id=group_id
            )
            self.logger.info('Пауза 40 сек')
            time.sleep(40)

        card_external_ids_to_bind_group = [
            card['id'] for card in remote_cards
            if card['id'] in card_external_ids and card['group_id'] != group_id
        ]

        card_list = [{"id": card_ext_id, "type": "Attach"} for card_ext_id in card_external_ids_to_bind_group]
        data = {
            "contract_id": self.contract_id,
            "group_id": group_id,
            "cards_list": json.dumps(card_list)
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
            raise CeleryError(message="Не удалось привязать карты к группе. Ответ API ГПН: "
                                      f"{res['status']['errors']}. Наш запрос: {data}")

    def unbind_cards_from_group(self, card_numbers: List[str], card_external_ids: List[str], group_id: str) -> None:
        # Открепляем карты от группы
        card_list = [{"id": card_id, "type": "Detach"} for card_id in card_external_ids]
        if not card_list:
            return None

        data = {
            "contract_id": self.contract_id,
            "group_id": group_id,
            "cards_list": json.dumps(card_list)
        }
        response = requests.post(
            url=self.endpoint(self.api_v1, "setCardsToGroup"),
            headers=self.headers | {"session_id": self.api_session_id},
            data=data
        )
        res = response.json()
        if res['status']['code'] != 200:
            self.logger.error("Не удалось открепить карту от группы. Ответ API ГПН: "
                              f"{res['status']['errors']}. Наш запрос: {data}")

        self.logger.info(f"От группы {group_id} откреплены карты {', '.join(card_numbers)}")
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

        # Если переданное в функцию количество дней превышает значение 28 (минимальное кол-во дней в месяце),
        # то забираем транзакции из ГПН внесколько итераций, пока не заберем данные за весь период
        transactions = []

        def request_transactions(_date_from: date, _date_to: date):
            page_offset = 0
            i = 0
            while True:
                # Цитата из документации на API:
                # Количество транзакций на странице. 500, если не указано.
                params = {
                    "date_from": _date_from.isoformat(),
                    "date_to": _date_to.isoformat(),
                    "page_limit": 500,
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

                if not res["data"]["total_count"]:
                    break

                transactions.extend(res["data"]["result"])
                # ('----------------------')
                # print(f'OFFSET: {page_offset}')
                # print(res["data"]["result"])
                page_offset += 500
                i += 1
                if i == 3:
                    break

        period = transaction_days
        date_from = self.today - timedelta(days=period)
        date_to = date_from + timedelta(days=min(period, 28))
        request_transactions(date_from, date_to)
        while date_to < self.today:
            date_from = date_to + timedelta(days=1)
            period = (self.today - date_from).days
            date_to = date_from + timedelta(days=min(period, 28))
            request_transactions(date_from, date_to)

        for transaction in transactions:
            transaction['timestamp'] = datetime.fromisoformat(transaction['timestamp'][:19])

        return transactions

    def set_group_limit(self, limit_id: str | None, group_id: str, product_category: GpnGoodsCategory,
                        limit_sum: int) -> str | None:

        new_limit = {
            "contract_id": self.contract_id,
            "group_id": group_id,
            "productType": product_category.value["id"],
            "sum": {
                "currency": "810",
                "value": limit_sum
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
        if res["status"]["code"] == 200:
            time.sleep(0.4)

            # Возвращаем идентификатор созданного лимита
            return res["data"][0]
        else:
            self.logger.error(f"Ошибка при установке группового лимита. Ответ сервера API: "
                              f"{res['status']['errors']}. Наш запрос: {data}")

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
            raise CeleryError(message=f"Ошибка при удалении лимита группы карт. Ответ сервера API: "
                                      f"{res['status']['errors']}. Наш запрос: {data}")

        self.logger.info(f"Удален лимит группы карт {data}")
        time.sleep(0.4)

    def delete_card_limit(self, limit_id: str) -> None:
        data = {
            "contract_id": self.contract_id,
            "limit_id": limit_id,
        }

        response = requests.post(
            url=self.endpoint(self.api_v1, "removeLimit"),
            headers=self.headers | {"session_id": self.api_session_id},
            data=data
        )
        res = response.json()

        if res["status"]["code"] != 200:
            raise CeleryError(message=f"Ошибка при удалении лимита карты. Ответ сервера API: "
                                      f"{res['status']['errors']}. Наш запрос: {data}")

        self.logger.info(f"Удален лимит карты {data}")
        time.sleep(0.4)

    def get_card_group_limits(self, group_id: str) -> List[Dict[str, Any]] | None:
        """
        Лимиты можно получить либо привязанные к договору, либо привязанные к группе карт, либо по конкретной карте.
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

        if res["status"]["code"] == 200:
            limits = res["data"]["result"]
            return limits

        else:
            self.logger.error(f"Ошибка при получении групповых лимитов ГПН. Ответ сервера API: "
                              f"{res['status']['errors']}. Наш запрос: {params}")

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

    def set_card_limit(self, card_id: str, gpn_goods_category: GpnGoodsCategory, goods_group_id: str | None, value: int,
                       unit: Unit, period: LimitPeriod) -> str:
        new_limit = {
            "contract_id": self.contract_id,
            "card_id": card_id,
            "productType": gpn_goods_category.value["id"],
            "term": {"type": 1},
        }
        if goods_group_id:
            new_limit["productGroup"] = goods_group_id

        if unit == Unit.RUB:
            new_limit["sum"] = {"currency": "810", "value": value}
        elif unit == Unit.LITERS:
            new_limit["amount"] = {"unit": "LIT", "value": value}
        elif unit == Unit.ITEMS:
            new_limit["amount"] = {"unit": "IT", "value": value}

        if period == LimitPeriod.DAY:
            new_limit["time"] = {"number": 1, "type": 3}
        elif period == LimitPeriod.MONTH:
            new_limit["time"] = {"number": 1, "type": 5}

        data = {"limit": json.dumps([new_limit])}
        response = requests.post(
            url=self.endpoint(self.api_v1, "setLimit"),
            headers=self.headers | {"session_id": self.api_session_id},
            data=data
        )
        res = response.json()

        if res["status"]["code"] != 200:
            raise CeleryError(message=f"Ошибка при установке лимита по карте. Ответ сервера API: "
                                      f"{res['status']['errors']}. Наш запрос: {data}")

        self.logger.info(f"Установлен лимит по карте {new_limit}")
        time.sleep(0.4)
        return res["data"][0]

    def get_stations(self) -> List[Dict[str, Any]]:
        params = {
            "page": 1,
            "onpage": 0
        }
        response = requests.get(
            url=self.endpoint(self.api_v1, "AZS", params=params),
            headers=self.headers | {"session_id": self.api_session_id}
        )
        res = response.json()

        if res["status"]["code"] != 200:
            raise CeleryError(message=f"Ошибка при получении списка АЗС. Ответ сервера API: "
                                      f"{res['status']['errors']}.")

        return res["data"]["result"]

    def get_transaction_details(self, external_id: int) -> List[Dict[str, Any]]:
        response = requests.get(
            url=self.endpoint(self.api_v2, f"transactions/{external_id}"),
            headers=self.headers | {"session_id": self.api_session_id}
        )
        res = response.json()

        if res["status"]["code"] != 200:
            raise CeleryError(message=f"Ошибка при получении данных по транзакции. Ответ сервера API: "
                                      f"{res['status']['errors']}.")

        return res["data"]["result"]

    def get_countries(self) -> List[Dict[str, Any]]:
        countries = self.get_dictionary(dictionary_name="Country")
        return countries

    def get_regions(self) -> List[Dict[str, Any]]:
        regions = self.get_dictionary(dictionary_name="Region")
        return regions
