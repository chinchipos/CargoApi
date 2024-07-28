from enum import Enum

from src.database.model.models import Transaction as TransactionOrm


class Action(Enum):
    NOTHING = "NOTHING"
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class WrappedTransaction:

    def __init__(self, transaction: TransactionOrm):
        self._data = {
            "obj": transaction,
            "action": Action.NOTHING
        }

    def transaction(self) -> TransactionOrm:
        return self._data["obj"]

    def action(self) -> Action:
        return self._data["action"]

    def mark_to_delete(self) -> None:
        self._data["action"] = Action.DELETE

    def mark_to_update(self) -> None:
        self._data["action"] = Action.UPDATE

    def update_overdraft_transaction(self, fee: float) -> None:
        self._data["obj"].transaction_sum = fee
        self._data["obj"].total_sum = fee
        self._data["action"] = Action.UPDATE
