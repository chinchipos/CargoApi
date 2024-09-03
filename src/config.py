import json

from dotenv import load_dotenv
import os
from datetime import timedelta, timezone
from pathlib import Path

load_dotenv()


# -----------------------------------------------------------
# Общие параметры
# -----------------------------------------------------------
PRODUCTION = True if os.environ.get('PRODUCTION').lower() == 'true' else False
JWT_SECRET = os.environ.get('JWT_SECRET')
SERVICE_TOKEN = os.environ.get('SERVICE_TOKEN')
SQLALCHEMY_ECHO = False
ROOT_DIR = Path(__file__).parent.parent
LOG_DIR = os.path.join(ROOT_DIR, "log")
TZ = timezone(offset=timedelta(hours=3), name='МСК')


# -----------------------------------------------------------
# Параметры подключения к REDIS
# -----------------------------------------------------------
REDIS_HOST = os.environ.get('REDIS_HOST')
REDIS_PORT = int(os.environ.get('REDIS_PORT'))
REDIS_USER = os.environ.get('REDIS_USER')
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD')


# -----------------------------------------------------------
# Параметры подключения к основной базе данных PostgreSQL
# -----------------------------------------------------------
DB_FQDN_HOST = os.environ.get('DB_FQDN_HOST')
DB_PORT = int(os.environ.get('DB_PORT'))
DB_NAME = os.environ.get('DB_NAME')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
SCHEMA = 'cargonomica'
PROD_URI = "postgresql+psycopg://{}:{}@{}:{}/{}".format(
    DB_USER,
    DB_PASSWORD,
    DB_FQDN_HOST,
    DB_PORT,
    DB_NAME
)


# -----------------------------------------------------------
# Встроенный суперадмин ПроАВТО
# -----------------------------------------------------------
BUILTIN_ADMIN_NAME = os.environ.get('BUILTIN_ADMIN_NAME')
BUILTIN_ADMIN_EMAIL = os.environ.get('BUILTIN_ADMIN_EMAIL')
BUILTIN_ADMIN_LASTNAME = os.environ.get('BUILTIN_ADMIN_LASTNAME')
BUILTIN_ADMIN_FIRSTNAME = os.environ.get('BUILTIN_ADMIN_FIRSTNAME')


# -----------------------------------------------------------
# Настройки почты
# -----------------------------------------------------------
MAIL_SERVER = os.environ.get("MAIL_SERVER")
MAIL_PORT = int(os.environ.get("MAIL_PORT"))
MAIL_USER = os.environ.get("MAIL_USER")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
MAIL_FROM = os.environ.get("MAIL_FROM")
OVERDRAFTS_MAIL_TO = json.loads(os.environ.get('OVERDRAFTS_MAIL_TO'))


# -----------------------------------------------------------
# Хабаровскнефтепродукт
# -----------------------------------------------------------
KHNP_URL = os.environ.get('KHNP_URL')
KHNP_USERNAME = os.environ.get('KHNP_USERNAME')
KHNP_PASSWORD = os.environ.get('KHNP_PASSWORD')


# -----------------------------------------------------------
# Газпромнефть
# -----------------------------------------------------------
GPN_URL = os.environ.get('GPN_URL')
GPN_USERNAME = os.environ.get('GPN_USERNAME')
GPN_PASSWORD = os.environ.get('GPN_PASSWORD')
GPN_TOKEN = os.environ.get('GPN_TOKEN')
GOODS_FILE_PATH = os.environ.get("GOODS_FILE_PATH")


# -----------------------------------------------------------
# ОПС
# -----------------------------------------------------------
if not PRODUCTION:
    OPS_SSH_HOST = os.environ.get('OPS_SSH_HOST')
    OPS_SSH_PORT = int(os.environ.get('OPS_SSH_PORT'))
    OPS_SSH_USER = os.environ.get('OPS_SSH_USER')
    OPS_SSH_PRIVATE_KEY_FILE = os.environ.get('OPS_SSH_PRIVATE_KEY_FILE')
OPS_SERVER = os.environ.get('OPS_SERVER')
OPS_PORT = int(os.environ.get('OPS_PORT'))
OPS_CONTRACT_ID = int(os.environ.get('OPS_CONTRACT_ID'))
