from src.celery_tasks.gpn.tasks import gpn_test

gpn_test.delay()
