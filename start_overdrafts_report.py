from src.celery.tasks.main import send_overdrafts_report

send_overdrafts_report.delay()
