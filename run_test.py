from src.celery_app.gpn.tasks import gpn_service_sync

# gpn_make_group_limits_check_report.delay()
gpn_service_sync.delay()
