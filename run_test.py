from src.celery_app.gpn.tasks import gpn_make_group_limits_check_report

gpn_make_group_limits_check_report.delay()
