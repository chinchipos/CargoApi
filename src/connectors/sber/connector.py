from datetime import date, timedelta, datetime
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, load_only, selectinload

from src.connectors.sber.sber_api import SberApi
from src.connectors.sber.statement import SberStatement
from src.database.models.user import UserOrm
from src.database.models.transaction import TransactionOrm
from src.database.models.money_receipt import MoneyReceiptOrm
from src.database.models.balance import BalanceOrm as BalanceOrm
from src.database.models.company import CompanyOrm as CompanyOrm
from src.repositories.base import BaseRepository

from sqlalchemy import select as sa_select, delete as sa_delete

from src.utils import enums


class SberConnector(BaseRepository):

    def __init__(self, session: AsyncSession, user: UserOrm | None = None):
        super().__init__(session, user)
        self.sber_api = SberApi()

    async def load_payments(self) -> None:
        """
        Прогрузка платежей, пополнение балансов.
        """

        # Получаем входящие платежи за текущий и предыдущий дни
        from_date = date.today() - timedelta(days=1)
        statement = self.sber_api.get_statement(from_date=from_date)

        # Получаем список ИНН плативших организаций
        payer_inn_list = statement.get_payer_inn_list()

        # Получаем балансы организаций
        balances = await self._get_balances(inn_list=payer_inn_list)

        # Получаем транзакции, пополнившие выбранные балансы за период
        balance_ids = [balance.id for balance in balances]
        transactions = await self._get_transactions(from_date=from_date, balance_ids=balance_ids)

        # Формируем список транзакции, которые присутствуют в локальной БД, но отсутствуют в выписке.
        await self._compare_transactions(transactions=transactions, statement=statement)

        # В объекте statement сейчас остались только транзакции, которых нет в БД.
        # Записываем их в БД.
        temp = await self._save_transactions(statement=statement)

        # Пересчитываем балансы
        # calc_balances

    async def _get_balances(self, inn_list: List[str]) -> List[BalanceOrm]:
        stmt = (
            sa_select(BalanceOrm)
            .options(
                load_only(BalanceOrm.id, BalanceOrm.balance, BalanceOrm.scheme)
            )
            .options(
                joinedload(BalanceOrm.company)
                .load_only(CompanyOrm.id, CompanyOrm.inn, CompanyOrm.name, CompanyOrm.personal_account)
            )
            .select_from(CompanyOrm, BalanceOrm)
            .where(CompanyOrm.inn.in_(inn_list))
            .where(BalanceOrm.company_id == CompanyOrm.id)
            .where(BalanceOrm.scheme == enums.ContractScheme.OVERBOUGHT)
        )
        print('-----------------------------------------')
        print('_get_balances')
        self.statement(stmt)
        balances = await self.select_all(stmt)
        return balances

    async def _get_transactions(self, from_date: date, balance_ids: List[str]) -> List[TransactionOrm]:
        stmt = (
            sa_select(TransactionOrm)
            .options(
                load_only(
                    TransactionOrm.id,
                    TransactionOrm.external_id,
                    TransactionOrm.date_time,
                    TransactionOrm.total_sum,
                    TransactionOrm.balance_id
                )
            )
            .options(
                selectinload(TransactionOrm.money_receipt)
                .load_only(MoneyReceiptOrm.id)
            )
            .where(TransactionOrm.date_time >= from_date)
            .where(TransactionOrm.is_debit.is_(False))
            .where(TransactionOrm.balance_id.in_(balance_ids))
        )
        print('-----------------------------------------')
        print('_get_transactions')
        self.statement(stmt)
        transactions = await self.select_all(stmt)
        return transactions

    async def _compare_transactions(self, transactions: List[TransactionOrm], statement: SberStatement) -> None:
        transactions_to_delete = []
        for transaction in transactions:
            transaction_exists = statement.exclude_payment_if_exists(
                operation_id=transaction.external_id,
                operation_date=transaction.date_time,
                amount=transaction.total_sum
            )
            if not transaction_exists:
                transactions_to_delete.append(transaction)

        # Удаляем из БД помеченные транзакции
        money_receipt_ids = [transaction.money_receipt.id for transaction in transactions_to_delete]
        stmt = (
            sa_delete(MoneyReceiptOrm)
            .where(MoneyReceiptOrm.id.in_(money_receipt_ids))
        )
        await self.session.execute(stmt)
        await self.session.commit()

        transaction_ids = [transaction.id for transaction in transactions_to_delete]
        stmt = (
            sa_delete(TransactionOrm)
            .where(TransactionOrm.id.in_(transaction_ids))
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def _save_transactions(self, statement: SberStatement, ) -> None:
        # Получаем ИНН организаций
        payer_inn_list = statement.get_payer_inn_list()

        # Получаем балансы организаций
        balances = await self._get_balances(inn_list=payer_inn_list)

        # Формируем вспомогательный словарь "ИНН" -> "balance_id"
        balance_id_by_inn = {balance.company.inn: balance.id for balance in balances}

        # Формируем набор данных для записи в таблицу транзакций
        dataset = []
        operation_ids = []
        for statement_date, accounts in statement.get_payments().items():
            for account, payments in accounts.items():
                for payment in payments:
                    inn = payment.get_payer_inn()
                    balance_id = balance_id_by_inn[inn] if inn in balance_id_by_inn else None
                    if balance_id:
                        operation_id = payment.get_operation_id()
                        operation_ids.append(operation_id)
                        transaction = dict(
                            external_id=operation_id,
                            date_time=payment.get_operation_date_time(),
                            date_time_load=datetime.now(),
                            is_debit=False,
                            balance_id=balance_id,
                            total_sum=payment.get_amount(),
                            comments=payment.get_purpose(),
                        )
                        dataset.append(transaction)

        # Записываем транзакции
        await self.bulk_insert_or_update(TransactionOrm, dataset)

        # Получаем из БД только что записанные транзакции. Нам нужно сформировать связь:
        # operation_id <--> TransactionOrm
        stmt = (
            sa_select(TransactionOrm)
            .options(
                load_only(TransactionOrm.id, TransactionOrm.external_id)
            )
            .where(TransactionOrm.external_id.in_(operation_ids))
        )
        transactions = await self.select_all(stmt)

        # Формируем вспомогательный словарь
        transaction_id_by_operation_id = {transaction.external_id: transaction.id for transaction in transactions}

        # Формируем набор данных для записи в таблицу автозачислений
        dataset = []
        for statement_date, accounts in statement.get_payments().items():
            for account, payments in accounts.items():
                for payment in payments:
                    inn = payment.get_payer_inn()
                    transaction_id = transaction_id_by_operation_id[inn] if inn in transaction_id_by_operation_id else None
                    transaction = dict(
                        bank=enums.Bank.SBER,
                        payment_id=payment.get_operation_id(),
                        payment_date_time=payment.get_operation_date_time(),
                        payment_company_name=payment.get_payer_name(),
                        payment_company_inn=inn,
                        payment_purpose=payment.get_purpose(),
                        amount=payment.get_amount(),
                        transaction_id=transaction_id
                    )
                    dataset.append(transaction)

        # Записываем историю автозачислений
        await self.bulk_insert_or_update(MoneyReceiptOrm, dataset)


"""
async def main():
    sber_api = SberApi()
    at, rt = await sber_api.init_tokens()
    print(at)
    print(rt)

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

asyncio.run(main())
"""

sber_api = SberApi()
# company_info = sber_api.get_company_info()
# pprint.pprint(company_info)
# begin_time = datetime.now()
s = sber_api.get_statement(from_date=date(2024, 8, 30))
# end_time = datetime.now()
s.print_payments()
# print(end_time - begin_time)
