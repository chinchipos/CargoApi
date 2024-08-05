from src.celery.gpn.tasks import sync_gpn_cards

sync_gpn_cards.delay()
