from dotenv import load_dotenv
import os
from datetime import timedelta, timezone


load_dotenv()
DB_FQDN_HOST = os.environ.get('DB_FQDN_HOST')
DB_PORT = os.environ.get('DB_PORT')
DB_NAME = os.environ.get('DB_NAME')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
SCHEMA = 'cargonomica'

JWT_SECRET = os.environ.get('JWT_SECRET')
SERVICE_TOKEN = os.environ.get('SERVICE_TOKEN')
PRODUCTION = True if os.environ.get('PRODUCTION') == 'true' else False
BUILTIN_ADMIN_NAME = os.environ.get('BUILTIN_ADMIN_NAME')
BUILTIN_ADMIN_EMAIL = os.environ.get('BUILTIN_ADMIN_EMAIL')
BUILTIN_ADMIN_LASTNAME = os.environ.get('BUILTIN_ADMIN_LASTNAME')
BUILTIN_ADMIN_FIRSTNAME = os.environ.get('BUILTIN_ADMIN_FIRSTNAME')

SQLALCHEMY_ECHO = os.environ.get('SQLALCHEMY_ECHO') == 'True'
LOG_DIR = os.environ.get('LOG_DIR')

TZ = timezone(offset=timedelta(hours=3), name='МСК')
