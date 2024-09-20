from src.celery_app.gpn.tasks import gpn_sync_card_states

gpn_sync_card_states.delay()
