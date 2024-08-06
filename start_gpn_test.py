from src.celery.gpn.tasks import gpn_test

gpn_test.delay()
