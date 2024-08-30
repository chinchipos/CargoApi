from datetime import datetime

from src.celery_app.balance.tasks import recalculate_transactions
from src.config import TZ

from_date_time = datetime.now(tz=TZ).replace(year=2024, month=8, day=28, hour=9, minute=0, second=0)
perconal_accounts = []
recalculate_transactions.delay(from_date_time, perconal_accounts)
