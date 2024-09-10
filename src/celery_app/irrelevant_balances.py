from datetime import datetime
from typing import Dict

from src.utils.enums import System


class IrrelevantBalances(dict):

    def __init__(self, system: System | None = None):
        self.irrelevant_balances = {}
        self.system = system
        self.sum_deltas: Dict[str, float] = {}
        dict.__init__(
            self,
            irrelevant_balances=self.irrelevant_balances,
            system=self.system,
            sum_deltas=self.sum_deltas
        )

    def add(self, balance_id: str, irrelevancy_date_time: datetime) -> None:
        try:
            if balance_id in self.irrelevant_balances:
                if irrelevancy_date_time < self.irrelevant_balances[balance_id]:
                    self.irrelevant_balances[balance_id] = irrelevancy_date_time
            else:
                self.irrelevant_balances[balance_id] = irrelevancy_date_time
        except Exception as e:
            print(f"Исключение: {str(e)}")
            print(self.irrelevant_balances)
            print(irrelevancy_date_time)

    def extend(self, another_irrelevantbalances_json: Dict[str, Dict[str, datetime]]) -> None:
        if another_irrelevantbalances_json:
            for balance_id, irrelevancy_date_time in another_irrelevantbalances_json["irrelevant_balances"].items():
                self.add(balance_id, irrelevancy_date_time)

    def data(self):
        return self.irrelevant_balances
