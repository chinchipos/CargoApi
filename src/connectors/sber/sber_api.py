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

import random
import string


class SberApi:

    def __init__(self):
        params = PROD_PARAMS if IS_PROD else TEST_PARAMS
        self._auth_url = params['auth_url']
        self._auth_api_url = params['auth_api_url']
        self._main_api_url = params['main_api_url']
        self._account_numbers = params['account_numbers']
        self._client_id = params['client_id']
        self._CS = params['client_secret']
        self._CS_expiration: date = params['client_secret_expiration']
        self._our_cert = params['our_cert']
        self._our_key = params['our_key']
        self._sber_cert = params['sber_cert']
        self._redirect_uri = REDIRECT_URI
        self._AT: str | None = None
        self._AT_expiration: datetime | None = None
        self._RT: str = params['refresh_token']
        self._RT_expiration: datetime = params['refresh_token_expiration']
        self._redis = redis.Redis(host='localhost', port=6379, decode_responses=True)
        self._redis_data_structure = "cargonomica_sber_credentials"

        self._init_credentials()

    def get_server_cert(self):
        server_cert = get_server_certificate(
            server="fintech.sberbank.ru",
            port=9443,
            our_cert_path=self._sber_cert,
            our_key_path=self._our_key
        )
        return server_cert

    def __is_access_token_expired(self):
        return datetime.now() > self._AT_expiration - timedelta(seconds=300) if self._AT_expiration else True

    def __is_refresh_token_expired(self):
        return datetime.now() > self._RT_expiration - timedelta(days=1)

    def __is_client_secret_expired(self):
        """
        Срок жизни CS - 40 дней. За 5 дней до окончания срока на почту приходит уведомление о необходимости смены CS.
        Чтобы работа велась гарантировано без уведомлений CS обновляется каждые 30 дней.
        """
        return date.today() > self._CS_expiration - timedelta(days=10)

    def __set_tokens(self, access_token: str, refresh_token: str) -> None:
        sber_api_logger.info(f"Получены новые Access Token и Refresh Token")
        self._AT = access_token
        self._AT_expiration = datetime.now() + timedelta(seconds=ACCESS_TOKEN_TTL_SECONDS)
        self._RT = refresh_token
        self._RT_expiration = datetime.now() + timedelta(days=REFRESH_TOKEN_TTL_DAYS)

        # Сохраняем токены в Redis
        sber_api_logger.info("Записываю Access Token и Refresh Token в хранилище Redis")
        credentials = {
            "AT": self._AT,
            "AT_expiration": self._AT_expiration.isoformat(),
            "RT": self._RT,
            "RT_expiration": self._RT_expiration.isoformat()
        }
        self._redis.hset(self._redis_data_structure, mapping=credentials)

    def __set_client_secret(self, client_secret: str, expiration_days: int) -> None:
        sber_api_logger.info(f"Получен новый CLIENT SECRET")
        self._CS = client_secret
        self._CS_expiration = datetime.now() + timedelta(days=expiration_days)

        # Сохраняем CLIENT SECRET в Redis
        sber_api_logger.info("Записываю CLIENT SECRET в хранилище Redis")
        credentials = {
            "CS": self._CS,
            "CS_expiration": self._CS_expiration.isoformat(),
        }
        self._redis.hset(self._redis_data_structure, mapping=credentials)

    def __request(self, endpoint_url: str, method: HttpMethod, params: Dict[str, str] | None = None) -> Response:
        if params:
            endpoint_url += "?" + "&".join([f"{key}={value}" for key, value in params.items()])

        session = requests.Session()
        if method == HttpMethod.GET:
            session.headers.update({
                'Accept': 'application/json',
                'Authorization': f'Bearer {self._AT}'
            })
        else:
            session.headers.update({
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            })

        session.verify = self._sber_cert
        session.cert = (self._our_cert, self._our_key)

        response = session.get(endpoint_url) if method == HttpMethod.GET else session.post(endpoint_url)

        # print(response)
        # print(response.text)
        return response

    def get_auth_link(self, use_token: bool = True) -> str:
        """
        https://developers.sber.ru/docs/ru/sber-api/authorization/overview#get-oauth-authorize
        """

        endpoint = AUTH_URL_TOKEN if use_token else self._auth_url
        request_url = (
            f"{endpoint}?"
            f"scope={SCOPE}&"
            f"response_type=code&"
            f"redirect_uri={self._redirect_uri}&"
            f"client_id={self._client_id}&"
            f"nonce={NONCE}&"
            f"state={STATE}"
        )
        return request_url

    def _init_credentials(self) -> None:
        """"
        Инициализирует Access Token (AT), Refresh Token (RT), Client Secret (CS) из хранилища Redis.
        Если в Redis не обнаружены эти данные, то выполняется следующее.
        Берется RT из конфигурационного файла, через Sber API идет обновление RT и получение AT,
        результат кэшируется в Redis.
        Берется CS из конфигурационного файла.
        Таким образом в Redis хранятся AT, RT, CS - при перезапуске CargoApi они не теряются.
        Формат хранящихся данных:
        {
            "AT": str,
            "AT_expiration": datetime,
            "RT": str,
            "RT_expiration": datetime,
            "CS": str,
            "CS_expiration": date,
        }
        """
        sber_api_logger.info('Запуск процедуры инициализации авторизационных данных')

        # Пытаемся получить авторизационные данные из хранилища Redis
        sber_api_logger.info('Поиск авторизационных данных (AT, RT, CS) в хранилище Redis')
        credentials = self._redis.hgetall(self._redis_data_structure)
        if credentials:
            sber_api_logger.info('Авторизационные данные найдены')

            # Сохраняем в переменные авторизационные данные
            self._AT = credentials.get('AT', None)
            if 'AT_expiration' in credentials:
                self._AT_expiration = datetime.fromisoformat(credentials['AT_expiration'])

            self._RT = credentials.get('RT', None)
            if 'RT_expiration' in credentials:
                self._RT_expiration = datetime.fromisoformat(credentials['RT_expiration'])

            self._CS = credentials.get('CS', None)
            if 'CS_expiration' in credentials:
                self._CS_expiration = date.fromisoformat(credentials['CS_expiration'])

        # Обновляем авторизационные данные, если необходимо
        self._update_credentials_if_required()

    def init_tokens_by_access_code(self, access_code: str) -> Tuple[str, str]:
        """"
        https://developers.sber.ru/docs/ru/sber-api/authorization/overview#post-access-token
        """
        endpoint_url = self._auth_api_url + "/v2/oauth/token"
        params = dict(
            grant_type="authorization_code",
            code=access_code,
            redirect_uri=self._redirect_uri,
            client_id=self._client_id,
            client_secret=self._CS,
        )
        response = self.__request(endpoint_url, HttpMethod.POST, params)
        print(response)
        print(response.text)
        if response.status_code == 200:
            response_data = response.json()
            self.__set_tokens(response_data['access_token'], response_data['refresh_token'])
        return self._AT, self._RT

    def _update_credentials_if_required(self) -> None:
        self._update_tokens_if_required()
        self._update_client_secret_if_required()

    def _update_tokens_if_required(self) -> None:
        """
        https://developers.sber.ru/docs/ru/sber-api/authorization/overview#post-refresh-token
        """
        sber_api_logger.info("Проверка валидности токенов.")

        if self.__is_refresh_token_expired():
            raise SberApiError(
                "Истек срок действия REFRESH_TOKEN. Требуется получить код авторизации, вручную получить "
                "Refresh Token и указать его в главном конфигурационном файле .env. "
                "Ссылка для запроса кода авторизации: "
                f"{self.get_auth_link(use_token=True)}"
            )

        if self.__is_access_token_expired():
            sber_api_logger.info("Истек срок действия Access Token. Запущена процедура обновления.")

            endpoint_url = self._auth_api_url + "/v2/oauth/token"
            params = dict(
                grant_type="refresh_token",
                refresh_token=self._RT,
                client_id=self._client_id,
                client_secret=self._CS,
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
            sber_api_logger.info(" -> Токены валидны, обновление не требуется")

    def _update_client_secret_if_required(self) -> None:
        """
        https://developers.sber.ru/docs/ru/sber-api/authorization/overview#client-secret
        """
        sber_api_logger.info("Проверка валидности CLIENT SECRET")

        if self.__is_client_secret_expired():
            sber_api_logger.info("Истек срок действия CLIENT SECRET. Запущена процедура обновления.")

            # Генерируем новый CLIENT_SECRET
            symbols = string.ascii_letters + string.digits
            new_client_secret = ''.join(random.sample(symbols, 8))

            endpoint_url = self._auth_api_url + "/v1/change-client-secret"
            params = dict(
                access_token=self._AT,
                client_id=self._client_id,
                client_secret=self._CS,
                new_client_secret=new_client_secret
            )
            response = self.__request(endpoint_url, HttpMethod.POST, params)
            if response.status_code == 200:
                response_data = response.json()
                self.__set_client_secret(
                    client_secret=new_client_secret,
                    expiration_days=response_data['clientSecretExpiration']
                )
            else:
                raise SberApiError(
                    message=(
                        "Ошибка при обновлении CLIENT SECRET через сервер Sber API.\n"
                        f"Код ответа сервера: {response.status_code}\n"
                        "Ответ сервера:\n"
                        f"{response.text}"
                    ),
                    trace=False
                )

        else:
            sber_api_logger.info(" -> CLIENT SECRET валиден, обновление не требуется")

    def get_company_info(self) -> Dict[str, str]:
        """
        https://developers.sber.ru/docs/ru/sber-api/host/company
        """

        sber_api_logger.info("Получение от Sber API информации по компании")
        self._update_credentials_if_required()
        endpoint_url = self._main_api_url + "/v1/client-info"
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

    def get_statement(self, from_date: date = date.today()) -> SberStatement:
        """
        https://developers.sber.ru/docs/ru/sber-api/host/transactions-02
        """

        sber_api_logger.info(f"Получение от Sber API выписки по счету с даты {from_date.isoformat()}")
        self._update_credentials_if_required()
        endpoint_url = self._main_api_url + "/v2/statement/transactions"
        statement = SberStatement(self._account_numbers)
        statement_date = from_date
        while statement_date <= date.today():
            for account_number in self._account_numbers:
                for page in range(1, 6):
                    params = dict(
                        accountNumber=account_number,
                        statementDate=statement_date.isoformat(),
                        page=page
                    )
                    response = self.__request(endpoint_url, HttpMethod.GET, params)
                    if response.status_code == 200:
                        statement.parse_api_statement(
                            statement_date=statement_date,
                            account=account_number,
                            api_statement=response.json()
                        )

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

            statement_date += timedelta(days=1)

        sber_api_logger.info("Выписка получена")
        return statement
