from typing import List

from sqlalchemy import select as sa_select

from datetime import datetime

from src.database import models
from src.repositories.base import BaseRepository
from src.repositories.company import CompanyRepository
from src.tasks.init import sync_task_logger


class CalcBalance(BaseRepository):

    async def get_initial_transaction(self, balance_id: str, from_date_time: datetime) -> models.Transaction:
        stmt = (
            sa_select(models.Transaction)
            .where(models.Transaction.balance_id == balance_id)
            .where(models.Transaction.date_time < from_date_time)
            .order_by(models.Transaction.date_time.desc())
            .limit(1)
        )
        transaction = await self.select_first(stmt)
        return transaction

    async def get_transactions_to_recalculate(
        self,
        balance_id: str,
        from_date_time: datetime
    ) -> List[models.Transaction]:
        stmt = (
            sa_select(models.Transaction)
            .where(models.Transaction.balance_id == balance_id)
            .where(models.Transaction.date_time >= from_date_time)
            .order_by(models.Transaction.date_time)
        )
        transactions = await self.select_all(stmt)
        return transactions

    async def calculate_transaction_balances(self, balance_id: str, from_date_time: datetime) -> None:
        # Получаем транзакцию компании, которая предшествует указанному времени
        initial_transaction = await self.get_initial_transaction(balance_id, from_date_time)

        # Получаем все транзакции компании по указанному балансу, начиная с указанного времени
        transactions_to_recalculate = await self.get_transactions_to_recalculate(balance_id, from_date_time)
        # print('====================================')
        # print('Транзакции для пересчета:')
        # for transaction in transactions_to_recalculate:
        #     print("ID: {}, Время: {}, Сумма: {}, Баланс: {}".format(
        #         transaction.id,
        #         transaction.date_time.isoformat().replace('T', ' '),
        #         transaction.total_sum,
        #         transaction.company_balance
        #     ))
        #     print('-----------')

        # Пересчитываем балансы
        previous_transaction = initial_transaction
        for transaction in transactions_to_recalculate:
            transaction.company_balance = previous_transaction.company_balance + transaction.total_sum
            previous_transaction = transaction

        # Сохраняем в БД
        dataset = []
        for transaction in transactions_to_recalculate:
            dataset.append({
                'id': transaction.id,
                'company_balance_after': transaction.company_balance,
            })
            await self.bulk_update(models.Transaction, dataset)

        # print('====================================')
        # print('Пересчитанные транзакции:')
        # ids = []
        # for transaction in transactions_to_recalculate:
        #     print("ID: {}, Время: {}, Сумма: {}, Баланс: {}".format(
        #         transaction.id,
        #         transaction.date_time.isoformat().replace('T', ' '),
        #         transaction.total_sum,
        #         transaction.company_balance
        #     ))
        #     print('-----------')
        #     ids.append(transaction.id)
#
        # print(', '.join(list(map(lambda x: str(x), ids))))

    async def calculate(self, calculation_info: dict) -> None:
        for balance_id, from_date_time in calculation_info.items():
            # Вычисляем и устанавливаем балансы в истории транзакций
            await self.calculate_transaction_balances(balance_id, from_date_time)

            # Устанавливаем текущий баланс организации
            company_repository = CompanyRepository(self.session, self.user)
            company, balance = await company_repository.set_company_balance_by_last_transaction(balance_id)
            sync_task_logger.info('Баланс организации {}: {} руб.'.format(company.name, balance))
