from datetime import datetime
from typing import Dict, List


class IrrelevantBalances(dict):

    def __init__(self, system_id: str | None = None):
        self.irrelevant_balances = {}
        self.system_id = system_id
        self.personal_accounts: List[str] = []
        dict.__init__(
            self,
            irrelevant_balances=self.irrelevant_balances,
            system_id=self.system_id,
            personal_accounts=self.personal_accounts
        )

    def add_balance_irrelevancy_date_time(self, balance_id: str, irrelevancy_date_time: datetime) -> None:
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

    def add_personal_account(self, personal_account: str) -> None:
        if personal_account not in self.personal_accounts:
            self.personal_accounts.append(personal_account)

    def extend(self, another_irrelevantbalances_json: Dict[str, Dict[str, datetime]]) -> None:
        if another_irrelevantbalances_json:
            for balance_id, irrelevancy_date_time in another_irrelevantbalances_json["irrelevant_balances"].items():
                self.add_balance_irrelevancy_date_time(balance_id, irrelevancy_date_time)

            for personal_account in another_irrelevantbalances_json["personal_accounts"]:
                if personal_account not in self.personal_accounts:
                    self.personal_accounts.append(personal_account)

    def data(self):
        return self.irrelevant_balances
