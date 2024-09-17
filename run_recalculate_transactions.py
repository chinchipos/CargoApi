from datetime import datetime

from src.celery_app.balance.tasks import recalculate_transactions

recalculate_transactions.delay(
    from_date_time=datetime(2024, 8, 1, 0, 0, 0),
    personal_accounts=["5850627"]
)
