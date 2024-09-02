from src.celery_app.ops.tasks import ops_import_cards

ops_import_cards.delay()
