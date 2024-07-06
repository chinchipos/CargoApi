import json
import os

"""Общие параметры"""
IS_PROD = False
REDIRECT_URI = "https://www.sberbank.ru/ru/person"
SCOPE = (
    "openid BANK_CONTROL_STATEMENT BANK_CONTROL_STATEMENT_CHANGE_APPLICATION BUSINESS_CARD_LIMIT "
    "BUSINESS_CARDS_TRANSFER CARD_ISSUE CERTIFICATE_REQUEST COLLECTION_ORDERS CONFIRMATORY_DOCUMENTS_INQUIRY "
    "CONTRACT_CLOSE_APPLICATION CORPORATE_CARD_REQUEST CORPORATE_CARDS CRYPTO_CERT_REQUEST_EIO CURR_BUY "
    "CURR_CONTROL_INFO_REQ CURR_CONTROL_MESSAGE_FROM_BANK CURR_CONTROL_MESSAGE_TO_BANK CURR_SELL CURRENCY_NOTICES "
    "CURRENCY_OPERATION_DETAILS DEBT_REGISTRY DICT ESTATE_FEED FILES GENERIC_LETTER_FROM_BANK GENERIC_LETTER_TO_BANK "
    "GET_CLIENT_ACCOUNTS GET_CORRESPONDENTS GET_CRYPTO_INFO GET_CRYPTO_INFO_EIO GET_REQUEST_STATISTICS "
    "GET_STATEMENT_ACCOUNT GET_STATEMENT_TRANSACTION ORDER_MANDATORY_SALE PAY_DOC_CUR PAY_DOC_RU accounts email "
    "individualExecutiveAgency inn name offerExpirationDate orgActualAddress orgFullName orgJuridicalAddress orgKpp "
    "orgLawForm orgLawFormShort OrgName orgOgrn orgOktmo phone_number terBank userPosition"
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

    # Номера счетов
    account_numbers = json.loads(os.environ.get('ACCOUNT_NUMBERS')),

    # Идентификатор клиента
    client_id = os.environ.get('CLIENT_ID'),

    # Пароль
    client_secret = "",

    # Сертификаты
    our_cert = os.path.join(os.getcwd(), 'CERTS', 'PROD', 'FINTECH_8772.pem'),
    sber_cert = os.path.join(os.getcwd(), 'CERTS', 'PROD', 'fintech-sberbank-ru-chain.pem')
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

    # Номер счета
    account_numbers = ["40702810706000001801"],

    # Идентификатор клиента
    client_id = "1958729756739688417",

    # Пароль
    client_secret = "eUsbBssP",

    # Сертификаты
    our_cert = os.path.join(os.getcwd(), 'CERTS', 'TEST', 'FINTECH05.pem'),
    sber_cert = os.path.join(os.getcwd(), 'CERTS', 'TEST', 'Russian_Trusted_Root_CA.pem')
)
