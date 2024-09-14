from src.celery_app.ops.tasks import ops_set_azs_tariffs

ops_set_azs_tariffs.delay()
