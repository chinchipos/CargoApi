import os

from dotenv import load_dotenv
load_dotenv()

SYSTEM_SHORT_NAME = 'ГПН'

GPN_URL = "https://api-demo.opti-24.ru"
# GPN_URL = "https://api.opti-24.ru"
GPN_USERNAME = os.environ.get('GPN_USERNAME')
GPN_PASSWORD = os.environ.get('GPN_PASSWORD')
GPN_TOKEN = os.environ.get('GPN_TOKEN')

# GPN_URL_TEST = "https://api-demo.opti-24.ru/vip/v1/"
# GPN_USERNAME_TEST = "demo"
# GPN_PASSWORD_TEST = "auto-generated-pas58-save-it"
# GPN_TOKEN_TEST = "GPN.3ce7b860ece5758d1d27c7f8b4796ea79b33927e.630c2bc76676191bd6e94222d9acaaf56bc0a750"
