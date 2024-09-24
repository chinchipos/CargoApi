from datetime import datetime
from typing import Dict, List


class IrrelevantBalances(dict):

    def __init__(self, system_id: str | None = None):
        self.irrelevant_balances = {}
        self.system_id = system_id
        self.increasing_total_sum_deltas: Dict[str, List[float]] = {}
        self.decreasing_total_sum_deltas: Dict[str, List[float]] = {}
        self.increasing_discount_fee_sum_deltas: Dict[str, List[float]] = {}
        self.decreasing_discount_fee_sum_deltas: Dict[str, List[float]] = {}
        dict.__init__(
            self,
            irrelevant_balances=self.irrelevant_balances,
            system_id=self.system_id,
            increasing_total_sum_deltas=self.increasing_total_sum_deltas,
            decreasing_total_sum_deltas=self.decreasing_total_sum_deltas,
            increasing_discount_fee_sum_deltas=self.increasing_discount_fee_sum_deltas,
            decreasing_discount_fee_sum_deltas=self.decreasing_discount_fee_sum_deltas
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
