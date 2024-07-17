import pprint
from datetime import date, datetime
from typing import List, Dict, Any

from src.connectors.sber.payment import SberPayment


class SberStatement:
    """
    _transactions = {
        statement_date: {
            account: List[SberPayment]]
        }
    }
    """
    def __init__(self, our_accounts: List[str]):
        self._payments: Dict[date, Dict[str, List[SberPayment]]] = {}
        self._our_accounts = our_accounts

    def parse_api_statement(self, statement_date: date, account: str, api_statement: Dict[str, Any]) -> None:
        for transaction in api_statement['transactions']:
            self.process_transaction(
                statement_date=statement_date,
                account=account,
                amount=float(transaction['amountRub']['amount']),
                direction=transaction['direction'],
                number=transaction['number'],
                operation_id=transaction['operationId'],
                operation_date_time=datetime.fromisoformat(transaction['operationDate']),
                payment_purpose=transaction['paymentPurpose'],
                payer_inn=transaction['rurTransfer'].get('payerInn', ''),
                payer_name=transaction['rurTransfer']['payerName'],
                payer_account=transaction['rurTransfer']['payerAccount'],
            )

    def process_transaction(self, statement_date: date, account: str, amount: float, direction: str, number: str,
                            operation_id: str, operation_date_time: datetime, payment_purpose: str,payer_inn: str,
                            payer_name: str, payer_account: str) -> None:

        if direction.upper() != 'CREDIT' or payer_account in self._our_accounts:
            return None

        payment = SberPayment(
            amount=amount,
            number=number,
            operation_id=operation_id,
            operation_date_time=operation_date_time,
            payment_purpose=payment_purpose,
            payer_inn=payer_inn,
            payer_name=payer_name
        )

        if statement_date not in self._payments:
            self._payments[statement_date] = {}
        date_payments = self._payments[statement_date]

        if account in date_payments:
            date_payments[account].append(payment)
        else:
            date_payments[account] = [payment]

    def print_payments(self):
        for statement_date, accounts in self._payments.items():
            print(f"Дата: {statement_date}")
            for account, payments in accounts.items():
                print(f"   Счет: {account}")
                for payment in payments:
                    print('      ---------------------')
                    payment_data = payment.get_data()
                    for key, value in payment_data.items():
                        print(f"      {key}: {value}")

    def get_payer_inn_list(self) -> List[str]:
        payer_inn_set = set()
        for statement_date, accounts in self._payments.items():
            for account, payments in accounts.items():
                for payment in payments:
                    payer_inn_set.add(payment.get_payer_inn())

        return list(payer_inn_set)

    def exclude_payment_if_exists(self, operation_id: str, operation_date: datetime, amount: float) -> bool:
        found = False
        for statement_date, accounts in self._payments.items():
            for account, payments in accounts.items():
                for payment in payments:
                    if operation_id == payment.get_operation_id() \
                            and operation_date == payment.get_operation_date_time() \
                            and amount == payment.get_amount():
                        payments.remove(payment)
                        found = True
                        return found

        return found

    def get_payments(self):
        return self._payments
