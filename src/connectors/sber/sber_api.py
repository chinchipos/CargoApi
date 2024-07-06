from datetime import datetime, timedelta, date
from typing import Tuple, Dict, Any

import requests
from requests import Response

from src.connectors.sber.config import IS_PROD, PROD_PARAMS, TEST_PARAMS, AUTH_URL_TOKEN, SCOPE, REDIRECT_URI, NONCE, \
    STATE, ACCESS_TOKEN_TTL_SECONDS, REFRESH_TOKEN_TTL_DAYS
from src.connectors.sber.exceptions import SberApiError
from src.utils.enums import HttpMethod


class SberApi:

    def __init__(self):
        params = PROD_PARAMS if IS_PROD else TEST_PARAMS
        self.auth_url = params['auth_url']
        self.auth_api_url = params['auth_api_url']
        self.main_api_url = params['main_api_url']
        self.account_numbers = params['account_numbers']
        self.client_id = params['client_id']
        self.client_secret = params['client_secret']
        self.our_cert = params['our_cert']
        self.sber_cert = params['sber_cert']
        self.redirect_uri = REDIRECT_URI
        self.access_token = ""
        self.access_token_expiration = datetime.now()
        self.refresh_token = ""
        self.refresh_token_expiration = datetime.now()

    def __is_access_token_expired(self):
        return datetime.now() < self.access_token_expiration - timedelta(seconds=300)

    def __is_refresh_token_expired(self):
        return datetime.now() < self.refresh_token_expiration - timedelta(seconds=300)

    def __set_tokens(self, access_token: str, refresh_token: str) -> None:
        self.access_token = access_token
        self.access_token_expiration = datetime.now() + timedelta(seconds=ACCESS_TOKEN_TTL_SECONDS)
        self.refresh_token = refresh_token
        self.refresh_token_expiration = datetime.now() + timedelta(days=REFRESH_TOKEN_TTL_DAYS)

    def __request(self, endpoint_url: str, method: HttpMethod, params: Dict[str, str] | None = None) -> Response:
        if params:
            endpoint_url += "?" + "&".join([key + "=" + value for key, value in params.items()])

        session = requests.Session()
        if method == HttpMethod.GET:
            session.headers.update({
                'Accept': 'application/json',
                'Authorization': f'Bearer {self.access_token}'
            })
        else:
            session.headers.update({
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
            })

        session.verify = self.sber_cert
        session.cert = self.our_cert

        response = session.get(endpoint_url) if method == HttpMethod.GET else session.post(endpoint_url)
        # print(response)
        # print(response.text)
        return response

    def get_auth_link(self, use_token: bool = True) -> str:
        """
        https://developers.sber.ru/docs/ru/sber-api/authorization/overview#get-oauth-authorize
        """

        endpoint = AUTH_URL_TOKEN if use_token else self.auth_url
        request_url = (
            f"{endpoint}?"
            f"scope={SCOPE}&"
            f"response_type=code&"
            f"redirect_uri={self.redirect_uri}&"
            f"client_id={self.client_id}&"
            f"nonce={NONCE}&"
            f"state={STATE}"
        )
        return request_url

    def init_tokens(self, access_code: str) -> Tuple[str, str]:
        """"
        https://developers.sber.ru/docs/ru/sber-api/authorization/overview#post-access-token
        """
        endpoint_url = self.auth_api_url + "/v2/oauth/token"
        params = dict(
            grant_type = "authorization_code",
            code = access_code,
            redirect_uri = self.redirect_uri,
            client_id = self.client_id,
            client_secret = self.client_secret,
        )
        response = self.__request(endpoint_url, HttpMethod.POST, params)
        # print(response)
        # print(response.text)
        response_data = response.json()
        self.__set_tokens(response_data['access_token'], response_data['refresh_token'])
        return self.access_token, self.refresh_token

    def update_tokens_if_necessary(self) -> Tuple[str, str]:
        """
        https://developers.sber.ru/docs/ru/sber-api/authorization/overview#post-refresh-token
        """
        if self.__is_refresh_token_expired():
            raise SberApiError(
                "Истек срок действия REFRESH_TOKEN, либо не была выполнена инициализация AT и RT токенов "
                "(функция init_tokens). При истечении срока действия токена требуется получить код авторизации, "
                "указать его в главном конфигурационном файле .env. Ссылка для запроса кода авторизации: "
                f"{self.get_auth_link(use_token = True)}"
            )

        if self.__is_access_token_expired():
            endpoint_url = self.auth_api_url + "/v2/oauth/token"
            params = dict(
                grant_type="refresh_token",
                refresh_token=self.refresh_token,
                client_id=self.client_id,
                client_secret=self.client_secret,
            )
            response = self.__request(endpoint_url, HttpMethod.POST, params)
            # print(response)
            # print(response.text)
            response_data = response.json()
            self.__set_tokens(response_data['access_token'], response_data['refresh_token'])
        return self.access_token, self.refresh_token

    def get_company_info(self) -> Dict[str, str]:
        """
        https://developers.sber.ru/docs/ru/sber-api/host/company
        """
        endpoint_url = self.main_api_url + "/v1/client-info"
        response = self.__request(endpoint_url, HttpMethod.GET)
        print('Code:', response, type(response))
        # print(response)
        # print(response.text)
        response_json = response.json()
        return response_json

    def get_statement(self, statement_date: date = date.today()) -> Dict[Any, Response]:
        """
        https://developers.sber.ru/docs/ru/sber-api/host/transactions-02
        """
        endpoint_url = self.main_api_url + "/v2/statement/transactions"
        output = {}
        for account_number in self.account_numbers:
            params = dict(
                accountNumber = account_number,
                statementDate = statement_date.isoformat(),
                page = 1
            )
            response = self.__request(endpoint_url, HttpMethod.POST, params)
            # print(output[account_number])
            # print(output[account_number].text)
            output[account_number] = response

        return output
