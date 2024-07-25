from datetime import datetime
from typing import Dict


class IrrelevantBalances(dict):

    def __init__(self):
        self.data = {}
        dict.__init__(self, data=self.data)

    def add(self, balance_id: str, irrelevancy_date_time: datetime) -> None:
        if balance_id in self.data:
            if irrelevancy_date_time < self.data[balance_id]:
                self.data[balance_id] = irrelevancy_date_time
        else:
            self.data[balance_id] = irrelevancy_date_time

    def extend(self, another_irrelevantbalances_data: Dict[str, datetime]) -> None:
        for balance_id, irrelevancy_date_time in another_irrelevantbalances_data.items():
            self.add(balance_id, irrelevancy_date_time)
