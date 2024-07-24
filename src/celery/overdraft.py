from datetime import datetime, timedelta
from time import sleep
from typing import List, Tuple

from sqlalchemy import select as sa_select, null
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.config import OVERDRAFT_FEE_PERCENT, TZ
from src.database.models import (User as UserOrm, Transaction as TransactionOrm, Balance as BalanceOrm,
                                 OverdraftsHistory as OverdraftsHistoryOrm)
from src.repositories.base import BaseRepository
from src.utils.enums import TransactionType
from src.utils.log import ColoredLogger

balance_id_str_type = str


class Overdraft(BaseRepository):

    def __init__(self, session: AsyncSession, user: UserOrm | None = None):
        super().__init__(session, user)
        self.logger = ColoredLogger(logfile_name='schedule.log', logger_name='OVERDRAFT')
        self.today = datetime.now(tz=TZ).date()
        self.yesterday = datetime.now(tz=TZ).date() - timedelta(days=1)

    async def calculate(self) -> None:
        # Получаем открытые овердрафты
        self.logger.info('Получаю из БД открытые овердрафты')
        opened_overdrafts = await self.get_opened_overdrafts()
        self.logger.info(f'Количетво открытых овердрафтов: {len(opened_overdrafts)}')

        # По открытым оверам анализируем последнюю транзакцию за вчерашний день.
        self.logger.info('Обрабатываю открытые овердрафты')
        await self.process_opened_overdrafts(opened_overdrafts)

        # По органищациям, у которых вчера не было открытого овера, получаем последнюю транзакцию за
        # вчерашний день и открываем овер при необходимости
        self.logger.info('Получаю из БД последние вчерашние транзакции по остальным организациям, '
                         'проверяю есть ли необходимость открыть новый овердрафт')
        last_transactions = await self.get_last_transactions(opened_overdrafts)
        self.logger.info(str(last_transactions))
        self.logger.info(f'Количетво транзакций: {len(last_transactions)}')

        self.logger.info('Обрабатываю последние вчерашние транзакции')
        await self.process_last_transactions(last_transactions)

    async def get_opened_overdrafts(self) -> Tuple[OverdraftsHistoryOrm, TransactionOrm]:
        # Формируем список открытых оверов и присоединяем к нему последнюю транзакцию за вчерашний день
        last_transaction_helper = (
            sa_select(TransactionOrm.id, TransactionOrm.balance_id)
            .where(TransactionOrm.date_time_load < self.today)
            .order_by(TransactionOrm.date_time_load.desc())
            .limit(1)
            .subquery(name="last_transaction_helper")
        )

        stmt = (
            sa_select(OverdraftsHistoryOrm, TransactionOrm)
            .options(
                joinedload(OverdraftsHistoryOrm.balance)
            )
            .where(OverdraftsHistoryOrm.end_date.is_(null()))
            .join(last_transaction_helper, last_transaction_helper.c.balance_id == OverdraftsHistoryOrm.balance_id)
            .join(TransactionOrm, TransactionOrm.id == last_transaction_helper.c.id)
        )
        opened_overdrafts = await self.select_all(stmt, scalars=False)
        return opened_overdrafts

    async def process_opened_overdrafts(self, opened_overdrafts: Tuple[OverdraftsHistoryOrm, TransactionOrm]) -> None:
        fee_transactions = []
        overdrafts_to_close = []
        for overdraft, last_transaction in opened_overdrafts:
            # Если баланс последней вчерашней транзакции ниже значения min_balance, то берем плату.
            # Если выше, то закрываем овер.
            fee_base = last_transaction.company_balance - overdraft.balance.min_balance
            fee = round(fee_base * OVERDRAFT_FEE_PERCENT / 100, 0) if fee_base < 0 else 0.0
            now = datetime.now(tz=TZ)
            if fee:
                # создаем транзакцию (плата за овер)
                fee_transaction = {
                    "date_time": now,
                    "date_time_load": now,
                    "transaction_type": TransactionType.OVERDRAFT_FEE,
                    "balance_id": overdraft.balance_id,
                    "transaction_sum": fee,
                    "total_sum": fee,
                    "company_balance": last_transaction.company_balance + fee,
                }
                sleep(0.001)
                fee_transactions.append(fee_transaction)

            else:
                # помечаем овер на закрытие
                overdraft_to_close = {"id": overdraft.id, "end_date": self.yesterday}
                overdrafts_to_close.append(overdraft_to_close)

        # Записываем в БД комиссионные транзакции
        await self.bulk_insert_or_update(TransactionOrm, fee_transactions)
        for fee_transaction in fee_transactions:
            self.logger.info(' ')
            self.logger.info(f'OPENED OVERDRAFTS: сформирована комиссия {fee_transaction}')

        # Закрываем в БД помеченные оверы
        await self.bulk_insert_or_update(OverdraftsHistoryOrm, overdrafts_to_close)
        self.logger.info(f'Количество погашенных овердрафтов {len(overdrafts_to_close)}')
        for overdraft_to_close in overdrafts_to_close:
            self.logger.info(' ')
            self.logger.info(f'OPENED OVERDRAFTS: закрыт овердрафт {overdraft_to_close}')

    async def get_last_transactions(self, opened_overdrafts: Tuple[OverdraftsHistoryOrm, TransactionOrm]) \
            -> List[TransactionOrm]:
        excluded_balance_ids = [overdraft.balance_id for overdraft, last_transaction in opened_overdrafts]
        stmt = (
            sa_select(TransactionOrm)
            .options(
                joinedload(TransactionOrm.balance)
                .joinedload(BalanceOrm.company)
            )
            .where(TransactionOrm.date_time_load < self.today)
            .where(TransactionOrm.balance_id.notin_(excluded_balance_ids))
            .order_by(TransactionOrm.date_time_load.desc())
            .limit(1)
        )
        last_transactions = await self.select_all(stmt)
        return last_transactions

    async def process_last_transactions(self, last_transactions: List[TransactionOrm]) -> None:
        fee_transactions = []
        overdrafts_to_open = []
        for last_transaction in last_transactions:
            # Если баланс последней вчерашней транзакции ниже значения min_balance, то берем плату и открываем овер.
            # Если выше, то ничего не делаем
            fee_base = last_transaction.company_balance - last_transaction.balance.min_balance
            fee = round(fee_base * OVERDRAFT_FEE_PERCENT / 100, 2) if fee_base < 0 else 0.0
            now = datetime.now(tz=TZ)
            if fee:
                # создаем транзакцию (плата за овер)
                fee_transaction = {
                    "date_time": now,
                    "date_time_load": now,
                    "transaction_type": TransactionType.OVERDRAFT_FEE,
                    "balance_id": last_transaction.balance_id,
                    "transaction_sum": fee,
                    "total_sum": fee,
                    "company_balance": last_transaction.company_balance + fee,
                }
                sleep(0.001)
                fee_transactions.append(fee_transaction)

                # помечаем овер на открытие
                overdraft_to_open = {
                    "balance_id": last_transaction.balance_id,
                    "days": last_transaction.balance.company.overdraft_days,
                    "sum": last_transaction.balance.company.overdraft_sum,
                    "begin_date": self.yesterday,
                    "end_date": None,
                }
                overdrafts_to_open.append(overdraft_to_open)

        # Записываем в БД комиссионные транзакции
        await self.bulk_insert_or_update(TransactionOrm, fee_transactions)
        for fee_transaction in fee_transactions:
            self.logger.info(' ')
            self.logger.info(f'LAST TRANSACTIONS: сформирована комиссия {fee_transaction}')

        # Открываем в БД новые овердрафты
        await self.bulk_insert_or_update(OverdraftsHistoryOrm, overdrafts_to_open)
        self.logger.info(f'Количество вновь открытых овердрафтов {len(overdrafts_to_open)}')
        for overdraft_to_open in overdrafts_to_open:
            self.logger.info(' ')
            self.logger.info(f'LAST TRANSACTIONS: открыт овердрафт {overdraft_to_open}')
