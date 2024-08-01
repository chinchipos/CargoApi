from src.celery.tasks.main import sync_gpn

sync_gpn.delay()
