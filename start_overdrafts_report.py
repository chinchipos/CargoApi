from src.celery_tasks.overdraft.tasks import send_overdrafts_report

send_overdrafts_report.delay()
