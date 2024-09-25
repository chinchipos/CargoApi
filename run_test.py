from src.celery_app.gpn.tasks import gpn_make_group_limits_check_report, service_sync

# gpn_make_group_limits_check_report.delay()
service_sync.delay()
