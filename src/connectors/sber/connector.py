import requests
import os
import base64
from authlib.jose import JsonWebSignature
import ssl

TEST = True


# Получение кода авторизации
"""
#authorize_endpoint = "https://efs-sbbol-ift-web.testsbi.sberbank.ru:9443/ic/sso/api/v2/oauth/authorize" if TEST else \
#    "https://sbi.sberbank.ru:9443/ic/sso/api/v2/oauth/authorize"
authorize_endpoint = "https://efs-sbbol-ift-web.testsbi.sberbank.ru:9443/ic/sso/api/v2/oauth/authorize" if TEST else \
    "http://localhost:28016/ic/sso/api/v2/oauth/authorize"

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
refresh_token = "c16665ef-19a7-4d75-ac12-2aeb82a9e43e-2"

request_url = (
    f"{oauth_token_endpoint}?"
    f"grant_type={grant_type}&"
    f"refresh_token={refresh_token}"
    f"client_id={CLIENT_ID}&"
    f"client_secret={CLIENT_SECRET}"
)
session = requests.Session()
session.headers.update({
    'Content-Type': 'application/x-www-form-urlencoded',
    'Accept': '*/*'
})
session.verify = SBER_ROOT_CA_CERT_PATH
session.cert = OUR_CERT_PATH
response = session.post(request_url)
print(response.text)
response_json = response.json()
AT = response_json['access_token']
RT = response_json['refresh_token']
"""
print('--------------')


# Получение профиля ОРГАНИЗАЦИИ
"""
endpoint = "https://iftfintech.testsbi.sberbank.ru:9443/fintech/api/v1/client-info" \
    if TEST else "https://fintech.sberbank.ru:9443/fintech/api/v1/client-info"

request_url = endpoint
session = requests.Session()
session.headers.update({
    'Authorization': f'Bearer 51a3fb31-d72d-4d7b-b06b-22addc36a150-2'
})
session.verify = SBER_ROOT_CA_CERT_PATH
session.cert = OUR_CERT_PATH
response = session.get(request_url)

print(response)
print(response.json())
"""


# Получение выписки

# Отправляем POST запрос на /fintech/api/v2/statement/transactions
# Цель: получить выписку
endpoint = "https://iftfintech.testsbi.sberbank.ru:9443/fintech/api/v2/statement/transactions" \
    if TEST else "https://fintech.sberbank.ru:9443/fintech/api/v2/statement/transactions"
account_number = "40702810706000001801"
statement_date = "2023-10-04"
page = 1


request_url = (
    f"{endpoint}?"
    f"accountNumber={account_number}&"
    f"statementDate={statement_date}&"
    f"page={page}"
)
session = requests.Session()
session.headers.update({
    'Accept': 'application/json',
    'Authorization': f'Bearer 51a3fb31-d72d-4d7b-b06b-22addc36a150-2'
})
session.verify = SBER_ROOT_CA_CERT_PATH
session.cert = OUR_CERT_PATH
response = session.get(request_url)
print(response)
print(response.text)

