import requests
import os
import ssl

TEST = True

CLIENT_ID = "1958729756739688417" if TEST else "8772"
CLIENT_SECRET = "eUsbBssP" if TEST else "58f4bc40-e5ac-4db3-97ae-e16c7b1a8a09"
REDIRECT_URI = "https://www.sberbank.ru/ru/person" if TEST else "https://www.sberbank.ru/ru/person"
SCOPE = (
    "openid BANK_CONTROL_STATEMENT BANK_CONTROL_STATEMENT_CHANGE_APPLICATION BUSINESS_CARD_LIMIT "
    "BUSINESS_CARDS_TRANSFER CARD_ISSUE CERTIFICATE_REQUEST COLLECTION_ORDERS CONFIRMATORY_DOCUMENTS_INQUIRY "
    "CONTRACT_CLOSE_APPLICATION CORPORATE_CARD_REQUEST CORPORATE_CARDS CRYPTO_CERT_REQUEST_EIO CURR_BUY "
    "CURR_CONTROL_INFO_REQ CURR_CONTROL_MESSAGE_FROM_BANK CURR_CONTROL_MESSAGE_TO_BANK CURR_SELL "
    "CURRENCY_NOTICES CURRENCY_OPERATION_DETAILS DEBT_REGISTRY DICT ESTATE_FEED FILES GENERIC_LETTER_FROM_BANK "
    "GENERIC_LETTER_TO_BANK GET_CLIENT_ACCOUNTS GET_CORRESPONDENTS GET_CRYPTO_INFO GET_CRYPTO_INFO_EIO "
    "GET_REQUEST_STATISTICS GET_STATEMENT_ACCOUNT GET_STATEMENT_TRANSACTION ORDER_MANDATORY_SALE PAY_DOC_CUR "
    "PAY_DOC_RU accounts email individualExecutiveAgency inn name offerExpirationDate orgActualAddress orgFullName "
    "orgJuridicalAddress orgKpp orgLawForm orgLawFormShort OrgName orgOgrn orgOktmo phone_number terBank userPosition"
) if TEST else (
    "openid BANK_CONTROL_STATEMENT BANK_CONTROL_STATEMENT_CHANGE_APPLICATION BUSINESS_CARD_LIMIT "
    "BUSINESS_CARDS_TRANSFER CARD_ISSUE CERTIFICATE_REQUEST COLLECTION_ORDERS CONFIRMATORY_DOCUMENTS_INQUIRY "
    "CONTRACT_CLOSE_APPLICATION CORPORATE_CARD_REQUEST CORPORATE_CARDS CRYPTO_CERT_REQUEST_EIO CURR_BUY "
    "CURR_CONTROL_INFO_REQ CURR_CONTROL_MESSAGE_FROM_BANK CURR_CONTROL_MESSAGE_TO_BANK CURR_SELL "
    "CURRENCY_NOTICES CURRENCY_OPERATION_DETAILS DEBT_REGISTRY DICT ESTATE_FEED FILES GENERIC_LETTER_FROM_BANK "
    "GENERIC_LETTER_TO_BANK GET_CLIENT_ACCOUNTS GET_CORRESPONDENTS GET_CRYPTO_INFO GET_CRYPTO_INFO_EIO "
    "GET_REQUEST_STATISTICS GET_STATEMENT_ACCOUNT GET_STATEMENT_TRANSACTION ORDER_MANDATORY_SALE PAY_DOC_CUR "
    "PAY_DOC_RU accounts email individualExecutiveAgency inn name offerExpirationDate orgActualAddress orgFullName "
    "orgJuridicalAddress orgKpp orgLawForm orgLawFormShort OrgName orgOgrn orgOktmo phone_number terBank userPosition"
)
NONCE = "80012c9c-1b9a-449e-a8d5-75100ea698ac"
STATE = "296014df-dbc8-4559-ab32-041bf5064a40"

OUR_CERT_PATH = os.path.join(os.getcwd(), 'CERTS', 'TEST', 'FINTECH05.pem') if TEST else \
    os.path.join(os.getcwd(), 'CERTS', 'PROD', 'FINTECH_8772.pem')

SBER_ROOT_CA_CERT_PATH = os.path.join(os.getcwd(), 'CERTS', 'TEST', 'Russian_Trusted_Root_CA.pem') if TEST else \
    os.path.join(os.getcwd(), 'CERTS', 'PROD', 'fintech-sberbank-ru-chain.pem')

# Получение кода авторизации
authorize_endpoint = "https://efs-sbbol-ift-web.testsbi.sberbank.ru:9443/ic/sso/api/v2/oauth/authorize" if TEST else \
    "https://sbi.sberbank.ru:9443/ic/sso/api/v2/oauth/authorize"
request_url = (
    f"{authorize_endpoint}?"
    f"scope={SCOPE}&"
    f"response_type=code&"
    f"redirect_uri={REDIRECT_URI}&"
    f"client_id={CLIENT_ID}&"
    f"nonce={NONCE}&"
    f"state={STATE}"
)

print('-------Запрос на авторизацию--------')
print(request_url)
print('------------------------------------')
"""
session = requests.Session()
print('SBER_ROOT_CA_CERT_PATH:', SBER_ROOT_CA_CERT_PATH)
session.verify = SBER_ROOT_CA_CERT_PATH
response = session.get(request_url)
print(response.text)
"""

# Получение AccessToken
"""
# Отправляем POST запрос на /ic/sso/api/v2/oauth/token
# Цель: получить AccessToken и RefreshToken
oauth_token_endpoint = "https://iftfintech.testsbi.sberbank.ru:9443/ic/sso/api/v2/oauth/token" if TEST else \
    "https://fintech.sberbank.ru:9443/ic/sso/api/v2/oauth/token"
grant_type = "authorization_code"
auth_code = "1bcbf79b-01d4-4077-9d17-a54145745930-2"

request_url = (
    f"{oauth_token_endpoint}?"
    f"grant_type={grant_type}&"
    f"code={auth_code}&"
    f"redirect_uri={REDIRECT_URI}&"
    f"client_id={CLIENT_ID}&"
    f"client_secret={CLIENT_SECRET}"
)
# pem = ssl.get_server_certificate(("fintech.sberbank.ru", 9443))
# print(pem)

session = requests.Session()
session.headers.update({
    'Content-Type': 'application/x-www-form-urlencoded',
    'Accept': 'application/json'
})

session.verify = SBER_ROOT_CA_CERT_PATH
session.cert = OUR_CERT_PATH
response = session.post(request_url)
print(response.text)
response_json = response.json()
AT = response_json['access_token']
RT = response_json['refresh_token']

print('--------------')
"""

# Обновление токенов
"""
# Отправляем POST запрос на /ic/sso/api/v2/oauth/token
# Цель: обновить AccessToken/RefreshToken
oauth_token_endpoint = "https://iftfintech.testsbi.sberbank.ru:9443/ic/sso/api/v2/oauth/token" if TEST else \
    "https://fintech.sberbank.ru:9443/ic/sso/api/v2/oauth/token"
grant_type = "refresh_token"
refresh_token = "c7a6b143-67a3-4887-8b0e-56b127dafd4a-2"

request_url = (
    f"{oauth_token_endpoint}?"
    f"grant_type={grant_type}&"
    f"refresh_token=ddb3fa4a-adc2-40e2-a8bf-15ac83f84869-2&"
    f"client_id={CLIENT_ID}&"
    f"client_secret={CLIENT_SECRET}"
)
session = requests.Session()
session.headers.update({
    'Content-Type': 'application/x-www-form-urlencoded',
    'Accept': 'application/json'
})
session.verify = SBER_ROOT_CA_CERT_PATH
session.cert = OUR_CERT_PATH
response = session.post(request_url)
print(response.text)
response_json = response.json()
AT = response_json['access_token']
RT = response_json['refresh_token']

print('--------------')
"""

# Получение выписки
"""
# Отправляем POST запрос на /fintech/api/v2/statement/transactions
# Цель: получить выписку
oauth_token_endpoint = "https://iftfintech.testsbi.sberbank.ru:9443/fintech/api/v2/statement/transactions" \
    if TEST else "https://fintech.sberbank.ru:9443/fintech/api/v2/statement/transactions"
account_number = "40702810138000191710"
statement_date = "2024-06-10"
page = 1

request_url = (
    f"{transactions_endpoint}?"
    f"accountNumber={account_number}&"
    f"statementDate={statement_date}&"
    f"page={page}"
)
session = requests.Session()
session.headers.update({
    'Accept': 'application/json',
    'Authorization': f'Bearer 29494144-792a-495b-b60a-553c032eb4ad-2'
})
session.verify = SBER_ROOT_CA_CERT_PATH
session.cert = OUR_CERT_PATH
response = session.get(request_url)
print(response)
print(response.text)
"""
