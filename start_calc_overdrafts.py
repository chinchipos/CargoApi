from src.celery.tasks import calc_overdrafts

calc_overdrafts.delay()
