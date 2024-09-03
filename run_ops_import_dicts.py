from src.celery_app.ops.tasks import ops_import_dicts

ops_import_dicts.delay()
