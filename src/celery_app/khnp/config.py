import os

from dotenv import load_dotenv
load_dotenv()

KHNP_URL = "http://clients.khnp.aoil.ru"
KHNP_USERNAME = os.environ.get('KHNP_USERNAME')
KHNP_PASSWORD = os.environ.get('KHNP_PASSWORD')
