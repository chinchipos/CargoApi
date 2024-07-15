import pprint
from datetime import date, datetime
from typing import List, Dict, Any

from src.connectors.sber.payment import SberPayment


class SberStatement:
    _accounts: Dict[str, List[SberPayment]] = {}

    def __init__(self, statement_date: date = date.today()):
        self._statement_date = statement_date

    def parse_api_statement(self, account: str, api_statement: Dict[str, Any]) -> None:
        for transaction in api_statement['transactions']:
            self.process_transaction(
                account=account,
                amount=transaction['amountRub']['amount'],
                direction=transaction['direction'],
                document_date=date.fromisoformat(transaction['documentDate']),
                number=transaction['number'],
                operation_date=datetime.fromisoformat(transaction['operationDate']),
                payment_purpose=transaction['paymentPurpose'],
                payer_inn=transaction['rurTransfer']['payerInn'],
                payer_name=transaction['rurTransfer']['payerName']
            )

    def process_transaction(self, account: str, amount: int, direction: str, document_date: date, number: str,
                            operation_date: datetime, payment_purpose: str, payer_inn: str, payer_name: str) -> None:
        if direction.upper() == 'CREDIT':
            payment = SberPayment(
                amount=amount,
                document_date=document_date,
                number=number,
                operation_date=operation_date,
                payment_purpose=payment_purpose,
                payer_inn=payer_inn,
                payer_name=payer_name
            )
            if account in self._accounts:
                self._accounts[account].append(payment)
            else:
                self._accounts[account] = [payment]

    def print_payments(self):
        print(f"Дата: {self._statement_date}")
        for account, payments in self._accounts.items():
            print(f"Счет: {account}")
            for payment in payments:
                print('   ---------------------')
                payment_data = payment.get_data()
                for key, value in payment_data.items():
                    print(f"   {key}: {value}")
