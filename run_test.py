from src.celery_app.gpn.tasks import gpn_sync_group_limits

gpn_sync_group_limits.delay()
