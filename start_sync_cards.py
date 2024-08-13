from src.celery_app.gpn.tasks import sync_gpn_cards

sync_gpn_cards.delay()
