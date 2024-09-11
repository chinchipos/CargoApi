from src.celery_app.gpn.tasks import gpn_service_sync

gpn_service_sync.delay()
