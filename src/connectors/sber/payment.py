from datetime import datetime
from typing import Dict, Any


class SberPayment:
    def __init__(self, amount: float, number: str, operation_id: str, operation_date_time: datetime,
                 payment_purpose: str, payer_inn: str, payer_name: str):
        self._amount = amount
        self._number = number
        self._operation_id = operation_id
        self._operation_date_time = operation_date_time
        self._payment_purpose = payment_purpose
        self._payer_inn = payer_inn
        self._payer_name = payer_name

    def get_data(self) -> Dict[str, Any]:
        output = dict(
            amount = self._amount,
            number = self._number,
            operation_id=self._operation_id,
            operation_date_time = self._operation_date_time,
            payment_purpose = self._payment_purpose,
            payer_inn = self._payer_inn,
            payer_name = self._payer_name
        )
        return output

    def get_amount(self):
        return self._amount

    def get_operation_id(self):
        return self._operation_id

    def get_operation_date_time(self):
        return self._operation_date_time

    def get_purpose(self):
        return self._payment_purpose

    def get_payer_inn(self):
        return self._payer_inn

    def get_payer_name(self):
        return self._payer_name


