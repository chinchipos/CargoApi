from src.celery_tasks.gpn.tasks import sync_gpn_cards

sync_gpn_cards.delay()
