from dotenv import load_dotenv
import os


load_dotenv()
DB_FQDN_HOST = os.environ.get('DB_FQDN_HOST')
DB_PORT = os.environ.get('DB_PORT')
DB_NAME = os.environ.get('DB_NAME')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
JWT_SECRET = os.environ.get('JWT_SECRET')
SERVICE_TOKEN = os.environ.get('SERVICE_TOKEN')
PRODUCTION = True if os.environ.get('PRODUCTION') == 'true' else False