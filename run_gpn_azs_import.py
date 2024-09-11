from src.celery_app.gpn.tasks import gpn_import_azs

gpn_import_azs.delay()
