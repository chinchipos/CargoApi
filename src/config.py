import json

from dotenv import load_dotenv
import os
from datetime import timedelta, timezone
from pathlib import Path


load_dotenv()

PRODUCTION = True if os.environ.get('PRODUCTION') == 'true' else False

DB_FQDN_HOST = os.environ.get('DB_FQDN_HOST')
DB_PORT = os.environ.get('DB_PORT')
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

JWT_SECRET = os.environ.get('JWT_SECRET')
SERVICE_TOKEN = os.environ.get('SERVICE_TOKEN')
BUILTIN_ADMIN_NAME = os.environ.get('BUILTIN_ADMIN_NAME')
BUILTIN_ADMIN_EMAIL = os.environ.get('BUILTIN_ADMIN_EMAIL')
BUILTIN_ADMIN_LASTNAME = os.environ.get('BUILTIN_ADMIN_LASTNAME')
BUILTIN_ADMIN_FIRSTNAME = os.environ.get('BUILTIN_ADMIN_FIRSTNAME')

SQLALCHEMY_ECHO = False
ROOT_DIR = Path(__file__).parent.parent
LOG_DIR = os.path.join(ROOT_DIR, "log")

TZ = timezone(offset=timedelta(hours=3), name='МСК')

MAIL_SERVER = os.environ.get("MAIL_SERVER")
MAIL_PORT = int(os.environ.get("MAIL_PORT"))
MAIL_USER = os.environ.get("MAIL_USER")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
MAIL_FROM = os.environ.get("MAIL_FROM")
OVERDRAFTS_MAIL_TO = json.loads(os.environ.get('OVERDRAFTS_MAIL_TO'))

GOODS_FILE_PATH = os.environ.get("GOODS_FILE_PATH")


if not PRODUCTION:
    OPS_SSH_HOST = os.environ.get('OPS_SSH_HOST')
    OPS_SSH_PORT = int(os.environ.get('OPS_SSH_PORT'))
    OPS_SSH_USER = os.environ.get('OPS_SSH_USER')
    OPS_SSH_PRIVATE_KEY_FILE = os.environ.get('OPS_SSH_PRIVATE_KEY_FILE')
OPS_SERVER = os.environ.get('OPS_SERVER')
OPS_PORT = int(os.environ.get('OPS_PORT'))
OPS_CONTRACT_ID = int(os.environ.get('OPS_CONTRACT_ID'))
