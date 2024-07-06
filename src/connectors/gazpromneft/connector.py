import json
from typing import Dict, Any, Tuple

import requests
import hashlib
from requests_toolbelt.utils import dump
from fake_useragent import UserAgent
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import PRODUCTION
from src.connectors.gazpromneft import config
from src.database.models import User
from src.repositories.base import BaseRepository

# print('-----------------------')
# print('Дамп запроса к API:')
# print(' ')
# data = dump.dump_all(response)
# print(data.decode('utf-8'))


class GPNConnector:

    # def __init__(self, session: AsyncSession, user: User | None = None):
    #     super().__init__(session, user)
    def __init__(self):
        self.api_url = config.GPN_URL if PRODUCTION else config.GPN_URL_TEST

        self.user_agent = UserAgent()
        api_key = config.API_KEY if PRODUCTION else config.API_KEY_TEST
        self.headers = {
            'user-agent': self.user_agent.random,
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'api_key': api_key
        }

    def endpoint(self, fn) -> str:
        return self.api_url + fn

    def auth_user(self) -> Tuple[str, str]:
        """Авторизация пользователя. Возвращает session_id."""

        api_username = config.USERNAME if PRODUCTION else config.USERNAME_TEST
        password = config.PASSWORD if PRODUCTION else config.PASSWORD_TEST
        password_hash = hashlib.sha512(password.encode('utf-8')).hexdigest().lower()

        response = requests.post(
            url=self.endpoint("authUser"),
            headers=self.headers,
            data={
                "login": api_username,
                "password": password_hash
            }
        )

        resp_data = response.json()
        # print(resp_data)
        _session_id = resp_data['data']['session_id']
        contract_id = resp_data['data']['contracts'][0]['id']
        return _session_id, contract_id

    def contract_info(self, _session_id: str, contract_id: str) -> Dict[str, Any]:
        """Получение информации об организации."""

        response = requests.get(
            url=self.endpoint("getPartContractData"),
            headers=self.headers | {"session_id": _session_id},
            data={"contract_id": contract_id}
        )

        return response.json()

    def get_balance(self, _session_id: str, contract_id: str) -> float:
        contract_data = self.contract_info(_session_id, contract_id)
        return float(contract_data['data']['balanceData']['balance'])


connector = GPNConnector()
_session_id, contract_id = connector.auth_user()
res = connector.get_balance(_session_id, contract_id)
print('Balance:', res)

# Нужна ли функция создания поставщика услуг? М/б стоит создавать его программно при новой интеграции?
