from src.celery_app.gpn.tasks import gpn_test

gpn_test.delay()
