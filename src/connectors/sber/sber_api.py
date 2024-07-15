from datetime import datetime, timedelta, date
from typing import Tuple, Dict

import redis
import requests
from requests import Response

from src.connectors.sber.config import IS_PROD, PROD_PARAMS, TEST_PARAMS, AUTH_URL_TOKEN, SCOPE, REDIRECT_URI, NONCE, \
    STATE, ACCESS_TOKEN_TTL_SECONDS, REFRESH_TOKEN_TTL_DAYS
from src.connectors.sber.exceptions import SberApiError, sber_api_logger
from src.connectors.sber.statement import SberStatement
from src.utils.common import get_server_certificate
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
        self.our_key = params['our_key']
        self.sber_cert = params['sber_cert']
        self.redirect_uri = REDIRECT_URI
        self.AT: str | None = None
        self.AT_expiration: datetime | None = None
        self.RT: str = params['refresh_token']
        self.RT_expiration: datetime = params['refresh_token_expiration']
        self.redis_ = redis.Redis(host='localhost', port=6379, decode_responses=True)

    def get_server_cert(self):
        server_cert = get_server_certificate(
            server="fintech.sberbank.ru",
            port=9443,
            our_cert_path=self.sber_cert,
            our_key_path=self.our_key
        )
        return server_cert

    def __is_access_token_expired(self):
        return datetime.now() > self.AT_expiration - timedelta(seconds=300) if self.AT_expiration else True

    def __is_refresh_token_expired(self):
        return datetime.now() > self.RT_expiration - timedelta(seconds=300)

    def __set_tokens(self, access_token: str, refresh_token: str) -> None:
        sber_api_logger.info(f"Получены новые Access Token и Refresh Token: {access_token} | {refresh_token}")
        self.AT = access_token
        self.AT_expiration = datetime.now() + timedelta(seconds=ACCESS_TOKEN_TTL_SECONDS)
        self.RT = refresh_token
        self.RT_expiration = datetime.now() + timedelta(days=REFRESH_TOKEN_TTL_DAYS)

        # Сохраняем токены в Redis
        sber_api_logger.info("Записываю Access Token и Refresh Token в хранилище Redis.")
        sber_tokens = {
            "AT": self.AT,
            "AT_expiration": self.AT_expiration.isoformat(),
            "RT": self.RT,
            "RT_expiration": self.RT_expiration.isoformat()
        }
        self.redis_.hset('sber_tokens', mapping=sber_tokens)

    def __request(self, endpoint_url: str, method: HttpMethod, params: Dict[str, str] | None = None) -> Response:
        if params:
            endpoint_url += "?" + "&".join([f"{key}={value}" for key, value in params.items()])

        session = requests.Session()
        if method == HttpMethod.GET:
            session.headers.update({
                'Accept': 'application/json',
                'Authorization': f'Bearer {self.AT}'
            })
        else:
            session.headers.update({
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
                # 'Authorization': f'Bearer {self.AT}'
            })

        session.verify = self.sber_cert
        session.cert = (self.our_cert, self.our_key)
        # session.cert = self.our_cert

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

    def init_tokens(self) -> None:
        """"
        Инициализирует AccessToken и RefreshToken из хранилища Redis. Если в Redis не обнаружены эти данные, то
        берется RefreshToken из конфигурационного файла, через Sber API идет обновление RT и получение AT,
        результат кэшируется в Redis.
        Таким образом в Redis хранятся AT и RT - при перезапуске CargoApi они не теряются.
        Формат хранящихся данных:
        sber_tokens = {
            "AT": "",
            "AT_expiration": datetime.now(),
            "RT": "",
            "RT_expiration": datetime.now(),
        }
        """
        # Пытаемся получить токены из хранилища Redis
        sber_api_logger.info('Поиск токенов в хранилище Redis')
        sber_tokens = self.redis_.hgetall('sber_tokens')
        if sber_tokens:
            sber_api_logger.info('Токены найдены:')
            sber_api_logger.info(f'AT: {sber_tokens['AT']} | {sber_tokens['AT_expiration'][:19].replace("T", " ")}')
            sber_api_logger.info(f'RT: {sber_tokens['RT']} | {sber_tokens['RT_expiration'][:19].replace("T", " ")}')

            # Сохраняем в переменные информацию о токенах
            self.AT = sber_tokens['AT']
            self.AT_expiration = datetime.fromisoformat(sber_tokens['AT_expiration'])
            self.RT = sber_tokens['RT']
            self.RT_expiration = datetime.fromisoformat(sber_tokens['RT_expiration'])

        # Обновляем токены, если необходимо
        self.update_tokens_if_required()

    def init_tokens_by_access_code(self, access_code: str) -> Tuple[str, str]:
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
        print(response)
        print(response.text)
        if response.status_code == 200:
            response_data = response.json()
            self.__set_tokens(response_data['access_token'], response_data['refresh_token'])
        return self.AT, self.RT

    def update_tokens_if_required(self) -> Tuple[str, str]:
        """
        https://developers.sber.ru/docs/ru/sber-api/authorization/overview#post-refresh-token
        """
        sber_api_logger.info("Проверка валидности токенов.")

        if self.__is_refresh_token_expired():
            raise SberApiError(
                "Истек срок действия REFRESH_TOKEN. Требуется получить код авторизации, вручную получить "
                "Refresh Token и указать его в главном конфигурационном файле .env. "
                "Ссылка для запроса кода авторизации: "
                f"{self.get_auth_link(use_token = True)}"
            )

        if self.__is_access_token_expired():
            sber_api_logger.info("Истек срок действия Access Token. Запущена процедура обновления.")

            endpoint_url = self.auth_api_url + "/v2/oauth/token"
            params = dict(
                grant_type="refresh_token",
                refresh_token=self.RT,
                client_id=self.client_id,
                client_secret=self.client_secret,
            )
            response = self.__request(endpoint_url, HttpMethod.POST, params)
            if response.status_code == 200:
                response_data = response.json()
                self.__set_tokens(response_data['access_token'], response_data['refresh_token'])
            else:
                raise SberApiError(
                    message=(
                        "Ошибка при обновлении токенов через сервер Sber API.\n"
                        f"Код ответа сервера: {response.status_code}\n"
                        "Ответ сервера:\n"
                        f"{response.text}"
                    ),
                    trace=False
                )

        else:
            sber_api_logger.info("Токены валидны, обновление не требуется")

        return self.AT, self.RT

    def get_company_info(self) -> Dict[str, str]:
        """
        https://developers.sber.ru/docs/ru/sber-api/host/company
        """
        sber_api_logger.info("Получение от Sber API информации по компании")
        endpoint_url = self.main_api_url + "/v1/client-info"
        response = self.__request(endpoint_url, HttpMethod.GET)
        if response.status_code == 200:
            return response.json()
        else:
            raise SberApiError(
                message=(
                    "Ошибка при запросе информации о компании через сервер Sber API.\n"
                    f"Код ответа сервера: {response.status_code}\n"
                    "Ответ сервера:\n"
                    f"{response.text}"
                ),
                trace=False
            )

    def get_statement(self, statement_date: date = date.today()) -> SberStatement:
        """
        https://developers.sber.ru/docs/ru/sber-api/host/transactions-02
        """
        sber_api_logger.info(f"Получение от Sber API Выписки по счету. Дата: {statement_date.isoformat()}")
        endpoint_url = self.main_api_url + "/v2/statement/transactions"
        statement = SberStatement(statement_date)
        for account_number in self.account_numbers:
            for page in range(1, 6):
                params = dict(
                    accountNumber = account_number,
                    statementDate = statement_date.isoformat(),
                    page = page
                )
                response = self.__request(endpoint_url, HttpMethod.GET, params)
                if response.status_code == 200:
                    statement.parse_api_statement(account=account_number, api_statement=response.json())

                elif response.status_code == 400 and response.json()['cause'].upper() == "WORKFLOW_FAULT":
                    # Закончились страницы
                    break

                else:
                    raise SberApiError(
                        message=(
                            "Ошибка при запросе выписки.\n"
                            f"Код ответа сервера: {response.status_code}\n"
                            "Ответ сервера:\n"
                            f"{response.text}"
                        ),
                        trace=False
                    )

        sber_api_logger.info("Выписка получена")
        return statement
