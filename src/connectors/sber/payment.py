from datetime import date
from typing import Dict, Any


class SberPayment:
    def __init__(self, amount: int, document_date: date, number: str, operation_date: date, payment_purpose: str,
                 payer_inn: str, payer_name: str):
        self._amount = amount
        self._document_date = document_date
        self._number = number
        self._operation_date = operation_date
        self._payment_purpose = payment_purpose
        self._payer_inn = payer_inn
        self._payer_name = payer_name

    def get_data(self) -> Dict[str, Any]:
        output = dict(
            amount = self._amount,
            document_date = self._document_date,
            number = self._number,
            operation_date = self._operation_date,
            payment_purpose = self._payment_purpose,
            payer_inn = self._payer_inn,
            payer_name = self._payer_name
        )
        return output
