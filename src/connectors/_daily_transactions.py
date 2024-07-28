from datetime import date
from typing import Dict, List

from src.config import OVERDRAFT_FEE_PERCENT
from src.connectors._wrapped_transaction import WrappedTransaction, Action
from src.database.model.models import Transaction as TransactionOrm
from src.utils.enums import TransactionType
from src.utils.log import ColoredLogger


class DailyTransactions:
    def __init__(self, irrelevant_transactions: List[WrappedTransaction],
                 initial_relevant_transaction: TransactionOrm, logger: ColoredLogger):
        self._data: Dict[date, List[WrappedTransaction]] = self._split_transactions_per_days(irrelevant_transactions)

        self._initial_relevant_transaction = initial_relevant_transaction

        self.logger = logger

    @staticmethod
    def _split_transactions_per_days(wrapped_transactions: List[WrappedTransaction]) \
            -> Dict[date, List[WrappedTransaction]]:
        splitted_transactions = {}
        for wrapped_transaction in wrapped_transactions:
            transaction_date = wrapped_transaction.transaction().date_time.date()
            if transaction_date in splitted_transactions:
                splitted_transactions[transaction_date].append(wrapped_transaction)
            else:
                splitted_transactions[transaction_date] = [wrapped_transaction]

        return dict(sorted(splitted_transactions.items()))

    def data(self) -> Dict[date, List[WrappedTransaction]]:
        return self._data

    def get_overdraft_transaction_by_date(self, day: date) -> WrappedTransaction | None:
        wrapped_transactions = self._data[day]
        overdraft_transactions = [
            t for t in wrapped_transactions
            if t.transaction().transaction_type == TransactionType.OVERDRAFT_FEE and t.action() != Action.DELETE
        ]

        if len(overdraft_transactions) > 1:
            # Если найдено более одной транзакции, то это ненормальная ситуация.
            # Логируем событие и помечаем транзакции на удаление
            self.logger.warning(
                f'Внимание! За дату {day.isoformat()} обнаружено несколько транзакций "Комиссия за овердрафт". '
                f'Помечаю их на удаление. IDs: {", ".join([t.transaction().id for t in overdraft_transactions])}'
            )
            for overdraft_transaction in overdraft_transactions:
                overdraft_transaction.mark_to_delete()

            return None

        elif len(overdraft_transactions) == 1:
            return overdraft_transactions[0]

        else:
            return None

    def create_overdraft_transaction(self, day: data, fee: float) -> None:
        pass

    def calc_transaction_balances_within_date(self, day: date) -> None:
        # Получаем последнюю транзакцию, предшествующую полученной дате
        dates = [day_ for day_ in self._data if day_ < day]
        if dates:
            last_date = dates[-1]
            previous_transaction = self._data[last_date][-1]
        else:
            previous_transaction = self._initial_relevant_transaction

        for current_transaction in self._data[day]:
            calculated_balance = (previous_transaction.transaction().company_balance +
                                  current_transaction.transaction().total_sum)
            if current_transaction.transaction().company_balance != calculated_balance:
                current_transaction.transaction().company_balance = calculated_balance
                current_transaction.mark_to_update()

            previous_transaction = current_transaction

    def calc_overdraft_fee(self, day: data) -> float:
        daily_transactions = self._data[day]
        if daily_transactions:
            last_transaction = daily_transactions[-1].transaction()
            fee_base = last_transaction.company_balance - last_transaction.balance.min_balance
            return fee_base * OVERDRAFT_FEE_PERCENT / 100 if fee_base < 0 else 0.0
        else:
            return 0.0
