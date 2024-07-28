from typing import List, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select as sa_select

from src.connectors.irrelevant_balances import IrrelevantBalances
from src.connectors._irrelevant_transactions import IrrelevantTransactions
from src.repositories.base import BaseRepository

from src.database.model.models import (User as UserOrm, OverdraftsHistory as OverdraftsHistoryOrm)

from src.utils.log import ColoredLogger


class Overdraft(BaseRepository):

    def __init__(self, session: AsyncSession, user: UserOrm | None = None):
        super().__init__(session, user)
        self.logger = ColoredLogger(logfile_name='schedule.log', logger_name='OVERDRAFT')
        self._irrelevant_balances = IrrelevantBalances()

    async def calculate(self, irrelevant_balances: IrrelevantBalances) -> None:
        # Получаем историю овердрафтов
        # overdrafts_history = await self.get_overdrafts_history(irrelevant_balances)

        # По каждому балансу циклически обрабатываем транзакции по дням:
        # 1. Проверяем наличие транзакции "Комиссия за овердрафт" - комиссия за пользование овердрафтом
        # взимается на следующий день. Если найдена и совпадает, то переходим к п.3. Если не найдена или отличается,
        # то формируем новую транзакцию или изменяем существующую (соответственно) и переходим к п.2.
        # 2. Пересчитываем транзакционные балансы за текущий день.
        # 3. Получаем последнюю транзакцию за текущий день. Если баланс на конец дня был отрицательным,
        # то формируем (но не записываем) новую транзакцию "Комиссия за овердрафт". Она пойдет в расчет
        # следующего дня.
        irrelevant_transactions = IrrelevantTransactions(self.session)
        await irrelevant_transactions.make_structure(irrelevant_balances)

        for balance_id, daily_transactions in irrelevant_transactions.data().items():
            calculated_overdraft_fee = 0.0
            for day in daily_transactions.data():
                # Проверяем в текущем дне наличие транзакции "Комиссия за овердрафт"
                overdraft_transaction = daily_transactions.get_overdraft_transaction_by_date(day)
                stored_overdraft_fee = overdraft_transaction.transaction().total_sum if overdraft_transaction else 0.0

                # Сопоставляем рассчитанную комиссию с полученной из БД.
                # В зависимости от комбинации выполняем соответствующее действие.
                if calculated_overdraft_fee:
                    if stored_overdraft_fee:
                        if calculated_overdraft_fee != stored_overdraft_fee:
                            overdraft_transaction.update_overdraft_transaction(calculated_overdraft_fee)
                    else:
                        daily_transactions.create_overdraft_transaction(day, calculated_overdraft_fee)

                else:
                    if stored_overdraft_fee:
                        daily_transactions.create_overdraft_transaction(day, calculated_overdraft_fee)
                    else:
                        pass

                # Пересчитываем балансы за текущую дату
                daily_transactions.calc_transaction_balances_within_date(day)

                # Вычисляем размер комиссии за пользование овердрафтом в текущей дате
                calculated_overdraft_fee = daily_transactions.calc_overdraft_fee(day)

        # Синхронизируем получившиеся транзакции с БД

    async def get_overdrafts_history(self, irrelevant_balances: IrrelevantBalances) \
            -> Dict[str, List[OverdraftsHistoryOrm]]:
        overdrafts_history = {}
        for balance_id, irrelevancy_date_time in irrelevant_balances.items():
            stmt = (
                sa_select(OverdraftsHistoryOrm)
                .where(OverdraftsHistoryOrm.balance_id == balance_id)
                .where(OverdraftsHistoryOrm.begin_date >= irrelevancy_date_time.date())
            )
            overdraft_history = await self.select_all(stmt)
            overdrafts_history[balance_id] = overdraft_history

        return overdrafts_history
