from sqlalchemy import select as sa_select

from datetime import datetime

from src.database import models
from src.repositories.base import BaseRepository
from src.repositories.company import CompanyRepository


class CalcBalance(BaseRepository):

    async def calculate(self, calculation_info: dict):
        for company_id, from_date_time in calculation_info.items():
            # Вычисляем и устанавливаем балансы в истории транзакций
            res = await self.calculate_transaction_balances(company_id, from_date_time)
            if not res['success']: return res

            # Устанавливаем текущий баланс организации
            repository = CompanyRepository(self.asession)
            res = await repository.set_company_balance_by_last_transaction(company_id)
            if not res['success']: return res

        return {'success': True}

    async def calculate_transaction_balances(self, company_id: str, from_date_time: datetime):
        # Получаем транзакцию компании, которая предшествует указанному времени
        res = await self.get_initial_transaction(company_id, from_date_time)
        if not res['success']: return res
        initial_transaction = res['transaction']
        print('initial_transaction:', initial_transaction)

        # Получаем все транзакции компании, начиная с указанного времени
        res = await self.get_transactions_to_recalculate(company_id, from_date_time)
        if not res['success']: return res
        transactions_to_recalculate = res['transactions']
        print('====================================')
        print('Транзакции для пересчета:')
        for transaction in transactions_to_recalculate:
            print("ID: {}, Время: {}, Сумма: {}, Баланс: {}".format(
                transaction.id,
                transaction.date_time.isoformat().replace('T', ' '),
                transaction.total_sum,
                transaction.company_balance_after
            ))
            print('-----------')

            # Пересчитываем балансы
        previous_transaction = initial_transaction
        for transaction in transactions_to_recalculate:
            transaction.company_balance_after = previous_transaction.company_balance_after + transaction.total_sum
            previous_transaction = transaction

        # Сохраняем в БД
        dataset = []
        for transaction in transactions_to_recalculate:
            dataset.append({
                'id': transaction.id,
                'company_balance_after': transaction.company_balance_after,
            })
            await self.bulk_update(models.Transaction, dataset)

        print('====================================')
        print('Пересчитанные транзакции:')
        ids = []
        for transaction in transactions_to_recalculate:
            print("ID: {}, Время: {}, Сумма: {}, Баланс: {}".format(
                transaction.id,
                transaction.date_time.isoformat().replace('T', ' '),
                transaction.total_sum,
                transaction.company_balance_after
            ))
            print('-----------')
            ids.append(transaction.id)

        print(', '.join(list(map(lambda x: str(x), ids))))

        return {'success': True}

    async def get_initial_transaction(self, company_id: str, from_date_time: datetime):
        stmt = (
            sa_select(models.Transaction)
            .where(models.Transaction.company_id == company_id)
            .where(models.Transaction.date_time < from_date_time)
            .order_by(models.Transaction.date_time.desc())
            .limit(1)
        )
        res = await self.select_first(stmt)
        if not res['success']: return res
        return {'success': True, 'transaction': res['data']}

    async def get_transactions_to_recalculate(self, company_id: str, from_date_time: datetime):
        stmt = (
            sa_select(models.Transaction)
            .where(models.Transaction.company_id == company_id)
            .where(models.Transaction.date_time >= from_date_time)
            .order_by(models.Transaction.date_time)
        )
        res = await self.select_all(stmt)
        if not res['success']: return res
        return {'success': True, 'transactions': res['data']}