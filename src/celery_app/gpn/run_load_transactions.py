from src.celery_app.gpn.api import GPNApi

gpn_api = GPNApi()
gpn_api.get_transactions(30)
