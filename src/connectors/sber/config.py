import json
import os
from datetime import datetime, date

from dotenv import load_dotenv
load_dotenv()

"""Общие параметры"""
IS_PROD = True
REDIRECT_URI = "https://www.sberbank.ru/ru/person"
SCOPE = (
    "GET_CLIENT_ACCOUNTS GET_STATEMENT_ACCOUNT PAY_DOC_RU PAYMENTS_REGISTRY DEBT_REGISTRY PAY_DOC_CUR "
    "CURR_CONTROL_MESSAGE_TO_BANK GET_CRYPTO_INFO CERTIFICATE_REQUEST ORDER_MANDATORY_SALE CURRENCY_NOTICES "
    "BANK_CONTROL_STATEMENT CURR_BUY CURR_SELL BANK_CONTROL_STATEMENT_CHANGE_APPLICATION CRYPTO_CERT_REQUEST_EIO "
    "GET_STATEMENT_TRANSACTION PAYROLL SALARY_AGREEMENT SALARY_AGREEMENT_REQUEST GET_CRYPTO_INFO_EIO "
    "CONTRACT_CLOSE_APPLICATION PAYMENT_REQUEST_IN COLLECTION_ORDERS GET_CORRESPONDENTS ESTATE_FEED "
    "FILES CONFIRMATORY_DOCUMENTS_INQUIRY GENERIC_LETTER_FROM_BANK CARD_ISSUE BUSINESS_CARD_LIMIT "
    "CURRENCY_OPERATION_DETAILS DICT GENERIC_LETTER_TO_BANK CURR_CONTROL_MESSAGE_FROM_BANK GET_REQUEST_STATISTICS "
    "CORPORATE_CARDS CORPORATE_CARD_REQUEST CURR_CONTROL_INFO_REQ BUSINESS_CARDS_TRANSFER OrgName "
    "individualExecutiveAgency name inn email phone_number orgKpp orgFullName orgOgrn orgActualAddress "
    "orgJuridicalAddress accounts orgOktmo terBank offerExpirationDate userPosition orgLawForm orgLawFormShort"
)
NONCE = "80012c9c-1b9a-449e-a8d5-75100ea698ac"
STATE = "296014df-dbc8-4559-ab32-041bf5064a40"
AUTH_URL_TOKEN = "http://localhost:28016/ic/sso/api/v2/oauth/authorize"
ACCESS_TOKEN_TTL_SECONDS = 3600
REFRESH_TOKEN_TTL_DAYS = 180

"""Параметры продуктового контура"""
PROD_PARAMS = dict(
    # Ссылка авторизации (вариант с СМС)
    auth_url = "https://sbi.sberbank.ru:9443/ic/sso/api/v2/oauth/authorize",

    # API методов авторизации
    auth_api_url = "https://fintech.sberbank.ru:9443/ic/sso/api",

    # API основных методов
    main_api_url = "https://fintech.sberbank.ru:9443/fintech/api",

    # Идентификатор клиента
    client_id=os.environ.get('CLIENT_ID'),

    # Номера счетов
    account_numbers = json.loads(os.environ.get('ACCOUNT_NUMBERS')),

    # Пароль
    client_secret = os.environ.get('CLIENT_SECRET'),
    client_secret_expiration = date.fromisoformat(os.environ.get('CLIENT_SECRET_EXPIRATION')),

    # Наш сертификат
    our_cert = os.path.join(os.getcwd(), 'CERTS', 'PROD', 'FINTECH_PROD_2024_CERT.pem'),

    # Наш закрытый ключ
    our_key = os.path.join(os.getcwd(), 'CERTS', 'PROD', 'FINTECH_PROD_2024_KEY.pem'),

    # Цепочка сертификатов сервера Сбера
    sber_cert = os.path.join(os.getcwd(), 'CERTS', 'PROD', 'fintech-sberbank-ru-chain.pem'),

    refresh_token = os.environ.get('REFRESH_TOKEN'),
    refresh_token_expiration = datetime.fromisoformat(os.environ.get('REFRESH_TOKEN_EXPIRATION'))
)


"""Параметры тестового контура"""
TEST_PARAMS = dict(
    # Ссылка авторизации (вариант с СМС)
    auth_url = "https://efs-sbbol-ift-web.testsbi.sberbank.ru:9443/ic/sso/api/v2/oauth/authorize",

    # СМС для тестов
    sms = "11111",

    # API методов авторизации
    auth_api_url = "https://iftfintech.testsbi.sberbank.ru:9443/ic/sso/api",

    # API основных методов
    main_api_url = "https://iftfintech.testsbi.sberbank.ru:9443/fintech/api",

    # Идентификатор клиента
    client_id = "1958729756739688417",

    # Номер счета
    account_numbers = ["40702810706000001801"],

    # Пароль
    client_secret = "eUsbBssP",

    # Сертификаты
    our_cert = os.path.join(os.getcwd(), 'CERTS', 'TEST', 'FINTECH05.pem'),
    sber_cert = os.path.join(os.getcwd(), 'CERTS', 'TEST', 'Russian_Trusted_Root_CA.pem')
)
