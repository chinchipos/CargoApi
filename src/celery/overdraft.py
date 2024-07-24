from datetime import datetime, timedelta
from time import sleep
from typing import List, Tuple

from sqlalchemy import select as sa_select, null
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.config import OVERDRAFT_FEE_PERCENT, TZ
from src.database.models import (User as UserOrm, Transaction as TransactionOrm, Balance as BalanceOrm,
                                 OverdraftsHistory as OverdraftsHistoryOrm, Company as CompanyOrm)
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
        self.balances_to_block_cards = set()
        self.fee_transactions = []
        self.overdrafts_to_open = []
        self.overdrafts_to_close = []
        self.overdrafts_to_off = []
        self.companies_to_disable_overdraft = []

    async def calculate(self) -> List[balance_id_str_type]:
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
        self.logger.info(f'Количетво транзакций: {len(last_transactions)}')

        self.logger.info('Обрабатываю последние вчерашние транзакции')
        await self.process_last_transactions(last_transactions)

        # Записываем в БД комиссионные транзакции
        await self.save_fee_transactions_to_db()

        # Записываем в БД погашенные оверы
        await self.save_closed_overdrafts()

        # Записываем в БД просроченные оверы
        await self.save_deleted_overdrafts()

        # Открываем в БД новые овердрафты
        await self.save_opened_overdrafts()

        self.logger.info(f'Количетво клиентов на блокировку карт: {len(self.balances_to_block_cards)}')
        return list(self.balances_to_block_cards)

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
                .joinedload(BalanceOrm.company)
            )
            .where(OverdraftsHistoryOrm.end_date.is_(null()))
            .join(last_transaction_helper, last_transaction_helper.c.balance_id == OverdraftsHistoryOrm.balance_id)
            .join(TransactionOrm, TransactionOrm.id == last_transaction_helper.c.id)
        )
        opened_overdrafts = await self.select_all(stmt, scalars=False)
        return opened_overdrafts

    async def process_opened_overdrafts(self, opened_overdrafts: Tuple[OverdraftsHistoryOrm, TransactionOrm]) -> None:
        for overdraft, last_transaction in opened_overdrafts:
            # Если баланс последней вчерашней транзакции ниже значения min_balance, то берем плату.
            # Если выше, то погашаем овер.
            fee_base = last_transaction.company_balance - overdraft.balance.min_balance
            fee = round(fee_base * OVERDRAFT_FEE_PERCENT / 100, 0) if fee_base < 0 else 0.0
            now = datetime.now(tz=TZ)
            if fee:
                # создаем транзакцию (плата за овер)
                self.add_fee_transaction(
                    date_time = now,
                    date_time_load = now,
                    transaction_type = TransactionType.OVERDRAFT_FEE,
                    balance_id = overdraft.balance_id,
                    fee_sum = fee,
                    company_balance = last_transaction.company_balance + fee,
                    min_balance=overdraft.balance.min_balance,
                    company=overdraft.balance.company
                )

                # Если овер открыт больше разрешенного времени, то помечаем его
                # для отключения насовсем и блокируем карты
                overdraft_opened_days = self.today - overdraft.begin_date
                if overdraft.balance.company.overdraft_days < overdraft_opened_days.days:
                    self.mark_overdraft_to_delete(
                        overdraft_id=overdraft.id,
                        company=overdraft.balance.company
                    )
                    self.mark_balance_to_block_cards(
                        balance_id=overdraft.balance_id,
                        company=overdraft.balance.company
                    )

            else:
                # помечаем овер на гашение
                self.mark_overdraft_to_close(
                    overdraft_id=overdraft.id,
                    company=overdraft.balance.company
                )

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
        for last_transaction in last_transactions:
            self.logger.info(
                f"{last_transaction.balance.company.name} | "
                f"sum: {last_transaction.total_sum} | "
                f"min_balance: {last_transaction.balance.min_balance} | "
                f"balance: {last_transaction.company_balance}"
            )
            # Если баланс последней вчерашней транзакции ниже значения min_balance, то при подключенном овере
            # берем плату и открываем овер, а при отключенном помечаем клиентов на блокировку карт.
            # Если выше, то ничего не делаем
            # min_balance - всегда меньше, либо равно нуля
            fee_base = last_transaction.company_balance - last_transaction.balance.min_balance
            fee = round(fee_base * OVERDRAFT_FEE_PERCENT / 100, 2) if fee_base < 0 else 0.0
            now = datetime.now(tz=TZ)
            if fee:
                # Попадаем сюда, если fee меньше нуля, то есть текущий баланс ниже значения min_balance
                if last_transaction.balance.company.overdraft_on:
                    # создаем транзакцию (плата за овер)
                    self.add_fee_transaction(
                        date_time=now,
                        date_time_load=now,
                        transaction_type=TransactionType.OVERDRAFT_FEE,
                        balance_id=last_transaction.balance_id,
                        fee_sum=fee,
                        company_balance=last_transaction.company_balance + fee,
                        min_balance=last_transaction.balance.min_balance,
                        company=last_transaction.balance.company
                    )

                    # помечаем овер на открытие
                    self.mark_overdraft_to_open(
                        balance_id=last_transaction.balance_id,
                        days=last_transaction.balance.company.overdraft_days,
                        overdraft_sum=last_transaction.balance.company.overdraft_sum,
                        company=last_transaction.balance.company
                    )

                else:
                    # Помечаем клиента на блокировку карт
                    self.mark_balance_to_block_cards(
                        balance_id=last_transaction.balance_id,
                        company=last_transaction.balance.company
                    )

    def add_fee_transaction(self, date_time: datetime, date_time_load: datetime, transaction_type: TransactionType,
                            balance_id: str, fee_sum: float, company_balance: float, min_balance: float,
                            company: CompanyOrm) -> None:
        fee_transaction = {
            "date_time": date_time,
            "date_time_load": date_time_load,
            "transaction_type": transaction_type,
            "balance_id": balance_id,
            "transaction_sum": fee_sum,
            "total_sum": fee_sum,
            "company_balance": company_balance,
        }
        sleep(0.001)
        self.fee_transactions.append(fee_transaction)
        self.logger.info(f'{company.name}: сформирована комиссия за пользование овердрафтом | '
                         f'fee_sum: {fee_sum} | '
                         f'balance: {company_balance} | '
                         f'min_balance: {min_balance}')

    async def save_fee_transactions_to_db(self) -> None:
        await self.bulk_insert_or_update(TransactionOrm, self.fee_transactions)

    def mark_overdraft_to_open(self, balance_id: str, days: int, overdraft_sum: float, company: CompanyOrm) -> None:
        overdraft_to_open = {
            "balance_id": balance_id,
            "days": days,
            "sum": overdraft_sum,
            "begin_date": self.yesterday,
            "end_date": None,
            "overdue": False,
        }
        self.overdrafts_to_open.append(overdraft_to_open)

        self.logger.info(f'{company.name}: пометка на открытие овердрафта')

    async def save_opened_overdrafts(self) -> None:
        await self.bulk_insert_or_update(OverdraftsHistoryOrm, self.overdrafts_to_open)
        self.logger.info(f'Количество вновь открытых овердрафтов {len(self.overdrafts_to_open)}')

    def mark_overdraft_to_delete(self, overdraft_id: str, company: CompanyOrm) -> None:
        overdraft_to_off = {"id": overdraft_id, "end_date": self.today, "overdue": True}
        self.overdrafts_to_off.append(overdraft_to_off)

        company_to_disable_overdraft = {"id": company.id, "overdraft_on": False}
        self.companies_to_disable_overdraft.append(company_to_disable_overdraft)

        self.logger.info(f'{company.name}: услуга овердрафт помечена на отключение '
                         'в связи с несоблюдением условий договора')

    async def save_deleted_overdrafts(self) -> None:
        await self.bulk_insert_or_update(OverdraftsHistoryOrm, self.overdrafts_to_off)
        self.logger.info(f'Количество просроченных овердрафтов {len(self.overdrafts_to_off)}')

        await self.bulk_insert_or_update(CompanyOrm, self.companies_to_disable_overdraft)

    def mark_overdraft_to_close(self, overdraft_id: str, company: CompanyOrm) -> None:
        overdraft_to_close = {"id": overdraft_id, "end_date": self.yesterday}
        self.overdrafts_to_close.append(overdraft_to_close)
        self.logger.info(f'{company.name}: текущий открытый овердрафт помечен на гашение '
                         'в связи с достаточностью средств на балансе')

    async def save_closed_overdrafts(self) -> None:
        await self.bulk_insert_or_update(OverdraftsHistoryOrm, self.overdrafts_to_close)

    def mark_balance_to_block_cards(self, balance_id: BalanceOrm, company: CompanyOrm) -> None:
        self.balances_to_block_cards.add(balance_id)
        self.logger.info(f'{company.name}: организация помечена на блокировку карт')
