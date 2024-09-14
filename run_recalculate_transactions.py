from datetime import datetime

from src.celery_app.balance.tasks import recalculate_transactions

from_date_time = datetime(2024, 9, 1, 0, 0, 0)
recalculate_transactions.delay(from_date_time=from_date_time)
