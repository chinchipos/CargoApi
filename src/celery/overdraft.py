import smtplib
from datetime import datetime, timedelta, date
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from time import sleep
from typing import List, Tuple, Dict

from sqlalchemy import select as sa_select, null, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, aliased

from src.config import TZ, MAIL_SERVER, MAIL_PORT, MAIL_USER, MAIL_PASSWORD, OVERDRAFTS_MAIL_TO, MAIL_FROM
from src.connectors.irrelevant_balances import IrrelevantBalances
from src.database.model.models import (Transaction as TransactionOrm, Balance as BalanceOrm, Company as CompanyOrm,
                                       OverdraftsHistory as OverdraftsHistoryOrm)
from src.reports.overdrafts import OverdraftsReport
from src.repositories.base import BaseRepository
from src.utils.enums import TransactionType, ContractScheme
from src.utils.log import ColoredLogger

balance_id_str_type = str


class Overdraft(BaseRepository):

    def __init__(self, session: AsyncSession, logger: ColoredLogger):
        super().__init__(session, None)
        self.logger = logger
        self.today = datetime.now(tz=TZ).date()
        self.yesterday = self.today - timedelta(days=1)
        self.tomorrow = self.today + timedelta(days=1)
        self.fee_transactions = []
        self.overdrafts_to_open = []
        self.overdrafts_to_close = []
        self.overdrafts_to_off = []
        self.companies_to_disable_overdraft = []

    async def calculate(self) -> IrrelevantBalances:
        # Получаем открытые овердрафты
        self.logger.info('Получаю из БД открытые овердрафты')
        opened_overdrafts = await self.get_opened_overdrafts()
        self.logger.info(f'Количетво открытых овердрафтов: {len(opened_overdrafts)}')

        # По открытым оверам анализируем последнюю транзакцию за вчерашний день.
        if opened_overdrafts:
            self.logger.info('Обрабатываю открытые овердрафты')
            await self.process_opened_overdrafts(opened_overdrafts)

        # По органищациям, у которых вчера не было открытого овера, получаем баланс на конец вчерашнего дня
        # и открываем овер при величине баланса ниже min_balance
        self.logger.info('По остальным организациям с подключенной услугой "овердрафт" получаю последние транзакции, '
                         'предшествующие сегодняшней дате . Проверяю есть ли необходимость открыть новый овердрафт')
        last_transactions = await self.get_last_transactions(opened_overdrafts)
        self.logger.info(f'Количетво транзакций: {len(last_transactions)}')

        if last_transactions:
            self.logger.info('Обрабатываю последние вчерашние транзакции')
            await self.process_last_transactions(last_transactions)

        # Записываем в БД комиссионные транзакции
        irrelevant_balances = await self.save_fee_transactions_to_db()

        # Записываем в БД погашенные оверы
        await self.save_closed_overdrafts()

        # Записываем в БД просроченные оверы
        await self.save_deleted_overdrafts()

        # Открываем в БД новые овердрафты
        await self.save_opened_overdrafts()

        # По помеченным балансам получаем карты на блокировку
        # card_repository = CardRepository(session=self.session)
        #  cards_to_block = await card_repository.get_cards_by_balance_ids(self.balances_to_block_cards)

        # Блокируем карты в локальной БД
        # Далее запустится задача синхронизации с системой и карты будут заблокированы в ней
        # dataset = [
        #     {
        #         "id": card.id,
        #         "is_active": False,
        #         "reason_for_blocking": BlockingCardReason.MANUALLY
        #     } for card in cards_to_block
        # ]
        # await self.bulk_update(CardOrm, dataset)

        # self.logger.info(f'Количетво клиентов на блокировку карт: {len(self.balances_to_block_cards)}')
        return irrelevant_balances

    async def get_opened_overdrafts(self) -> List[Tuple[OverdraftsHistoryOrm, TransactionOrm]]:
        # Формируем список открытых оверов и присоединяем к нему последнюю транзакцию, предшествующую сегодняшней дате
        balance_table = aliased(BalanceOrm, name="blnc")
        last_transaction_helper = (
            sa_select(TransactionOrm.id, TransactionOrm.balance_id)
            .select_from(TransactionOrm, balance_table)
            .where(TransactionOrm.balance_id == balance_table.id)
            .where(balance_table.scheme == ContractScheme.OVERBOUGHT)
            .where(TransactionOrm.date_time_load < self.today)
            .distinct(TransactionOrm.balance_id)
            .order_by(
                TransactionOrm.balance_id,
                TransactionOrm.date_time_load.desc()
            )
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
        # self.statement(stmt)
        dataset = await self.select_all(stmt, scalars=False)
        return dataset

    async def process_opened_overdrafts(self, opened_overdrafts: List[Tuple[OverdraftsHistoryOrm, TransactionOrm]]) \
            -> None:
        for overdraft, last_transaction in opened_overdrafts:
            # Если баланс последней вчерашней транзакции ниже значения min_balance, то берем плату.
            # Если выше, то погашаем овер.
            trigger = True if last_transaction.company_balance < overdraft.balance.company.min_balance else False
            if trigger:
                fee_base = last_transaction.company_balance - overdraft.balance.company.min_balance
                fee_sum = round(fee_base * overdraft.balance.company.overdraft_fee_percent / 100, 0) \
                    if fee_base < 0 else 0.0

                # создаем транзакцию (плата за овер)
                self.add_fee_transaction(balance_id=overdraft.balance_id, fee_sum=fee_sum)
                self.log_decision(
                    company=overdraft.balance.company,
                    transaction_balance=last_transaction.company_balance,
                    decision="начислить комиссию"
                )

                # Если овер открыт больше разрешенного времени, то помечаем его
                # для отключения насовсем. Блокировку карты выполнит следующая задача в Celery.
                overdraft_end_date = overdraft.begin_date + timedelta(days=overdraft.days - 1)
                overdraft_payment_deadline = overdraft_end_date + timedelta(days=1)
                if overdraft_payment_deadline < self.today:
                    self.mark_overdraft_to_delete(overdraft_id=overdraft.id, company=overdraft.balance.company)
                    # self.mark_balance_to_block_cards(balance_id=overdraft.balance_id)
                    self.log_decision(
                        company=overdraft.balance.company,
                        transaction_balance=last_transaction.company_balance,
                        decision='отключить услугу "овердрафт" в связи с нарушением условий договора'
                    )

            else:
                # помечаем овер на гашение
                self.mark_overdraft_to_close(overdraft_id=overdraft.id)
                self.log_decision(
                    company=overdraft.balance.company,
                    transaction_balance=last_transaction.company_balance,
                    decision="прекратить отсчет времени пользования овердрафтом"
                )

    async def get_last_transactions(self, opened_overdrafts: List[Tuple[OverdraftsHistoryOrm, TransactionOrm]]) \
            -> List[TransactionOrm]:

        balance_table = aliased(BalanceOrm, name="blnc")
        stmt = (
            sa_select(TransactionOrm)
            .options(
                joinedload(TransactionOrm.balance)
                .joinedload(BalanceOrm.company)
            )
            .select_from(TransactionOrm, balance_table)
            .where(TransactionOrm.balance_id == balance_table.id)
            .where(balance_table.scheme == ContractScheme.OVERBOUGHT)
            .where(TransactionOrm.date_time_load < self.today)
            .distinct(TransactionOrm.balance_id)
            .order_by(
                TransactionOrm.balance_id,
                TransactionOrm.date_time_load.desc()
            )
        )

        excluded_balance_ids = [overdraft.balance_id for overdraft, last_transaction in opened_overdrafts]
        if excluded_balance_ids:
            stmt = stmt.where(balance_table.id.notin_(excluded_balance_ids))

        # self.statement(stmt)

        last_transactions = await self.select_all(stmt)
        return last_transactions

    async def process_last_transactions(self, last_transactions: List[TransactionOrm]) -> None:
        for last_transaction in last_transactions:
            # Если баланс последней вчерашней транзакции ниже значения min_balance, то при подключенном овере
            # берем плату и открываем овер, а при отключенном помечаем клиентов на блокировку карт.
            # Если выше, то ничего не делаем
            # min_balance - всегда меньше, либо равно нулю
            # fee_base = last_transaction.company_balance - last_transaction.balance.company.min_balance
            trigger = True if last_transaction.company_balance < last_transaction.balance.company.min_balance \
                else False
            if not trigger:
                self.log_decision(
                    company=last_transaction.balance.company,
                    transaction_balance=last_transaction.company_balance,
                    decision="ничего не делать"
                )
            else:
                if last_transaction.balance.company.overdraft_on:
                    fee_base = last_transaction.company_balance
                    fee_sum = round(fee_base * last_transaction.balance.company.overdraft_fee_percent / 100, 2) \
                        if fee_base < 0 else 0.0

                    # создаем транзакцию (плата за овер)
                    self.add_fee_transaction(balance_id=last_transaction.balance_id, fee_sum=fee_sum)

                    # помечаем овер на открытие
                    self.mark_overdraft_to_open(
                        balance_id=last_transaction.balance_id,
                        days=last_transaction.balance.company.overdraft_days,
                        overdraft_sum=last_transaction.balance.company.overdraft_sum
                    )

                    self.log_decision(
                        company=last_transaction.balance.company,
                        transaction_balance=last_transaction.company_balance,
                        decision=f"начислить комиссию {fee_sum}, начать отсчет времени пользования овердрафтом"
                    )

    def add_fee_transaction(self, balance_id: str, fee_sum: float) -> None:
        now = datetime.now(tz=TZ)
        fee_transaction = {
            "date_time": now,
            "date_time_load": now,
            "transaction_type": TransactionType.OVERDRAFT_FEE,
            "balance_id": balance_id,
            "transaction_sum": fee_sum,
            "total_sum": fee_sum,
            "company_balance": 0,   # баланс посчитает следующая по цепочке задача Celery
        }
        sleep(0.001)
        self.fee_transactions.append(fee_transaction)

    async def save_fee_transactions_to_db(self) -> IrrelevantBalances:
        # Проверяем наличие комиссионной транзакции по этому балансу в текущую дату.
        # Если отсутствует, то создаем транзакцию в БД.
        stmt = (
            sa_select(TransactionOrm.balance_id)
            .where(TransactionOrm.date_time_load >= self.today)
            .where(TransactionOrm.date_time_load < self.today + timedelta(days=1))
            .where(TransactionOrm.transaction_type == TransactionType.OVERDRAFT_FEE)
        )
        dataset = await self.select_all(stmt, scalars=False)
        balance_ids = [data[0] for data in dataset]

        fee_transactions_to_save = [fee_transaction for fee_transaction in self.fee_transactions
                                    if fee_transaction["balance_id"] not in balance_ids]

        await self.bulk_insert_or_update(TransactionOrm, fee_transactions_to_save)
        self.logger.info(f'Количество комиссионных транзакций: {len(fee_transactions_to_save)}')

        irrelevant_balances = IrrelevantBalances()
        for transaction in fee_transactions_to_save:
            irrelevant_balances.add(
                balance_id=str(transaction['balance_id']),
                irrelevancy_date_time=transaction['date_time_load']
            )

        return irrelevant_balances

    def mark_overdraft_to_open(self, balance_id: str, days: int, overdraft_sum: float) -> None:
        overdraft_to_open = {
            "balance_id": balance_id,
            "days": days,
            "sum": overdraft_sum,
            "begin_date": self.yesterday,
            "end_date": None,
            "overdue": False,
        }
        self.overdrafts_to_open.append(overdraft_to_open)

    async def save_opened_overdrafts(self) -> None:
        await self.bulk_insert_or_update(OverdraftsHistoryOrm, self.overdrafts_to_open)
        self.logger.info(f'Количество вновь открытых овердрафтов: {len(self.overdrafts_to_open)}')

    def mark_overdraft_to_delete(self, overdraft_id: str, company: CompanyOrm) -> None:
        overdraft_to_off = {"id": overdraft_id, "end_date": self.today, "overdue": True}
        self.overdrafts_to_off.append(overdraft_to_off)

        company_to_disable_overdraft = {"id": company.id, "overdraft_on": False}
        self.companies_to_disable_overdraft.append(company_to_disable_overdraft)

    async def save_deleted_overdrafts(self) -> None:
        await self.bulk_insert_or_update(OverdraftsHistoryOrm, self.overdrafts_to_off)
        self.logger.info(f'Количество просроченных овердрафтов: {len(self.overdrafts_to_off)}')

        await self.bulk_insert_or_update(CompanyOrm, self.companies_to_disable_overdraft)

    def mark_overdraft_to_close(self, overdraft_id: str) -> None:
        overdraft_to_close = {"id": overdraft_id, "end_date": self.yesterday}
        self.overdrafts_to_close.append(overdraft_to_close)

    async def save_closed_overdrafts(self) -> None:
        await self.bulk_insert_or_update(OverdraftsHistoryOrm, self.overdrafts_to_close)
        self.logger.info(f'Количество погашенных овердрафтов: {len(self.overdrafts_to_close)}')

    # def mark_balance_to_block_cards(self, balance_id: BalanceOrm) -> None:
    #    self.balances_to_block_cards.add(balance_id)

    def log_decision(self, company: CompanyOrm, transaction_balance: float, decision: str) -> None:
        message = (
            f"услуга овердрафт: {'подключена' if company.overdraft_on else 'не подключена'} | "
            f"{company.name} | "
            f"min_balance: {company.min_balance} | "
            f"overdraft_sum: {company.overdraft_sum} | "
            f"balance: {transaction_balance} | "
            f"действие: {decision}"
        )
        self.logger.info(message)

    async def send_opened_overdrafts_report(self) -> None:
        # Получаем все открытые овердрафты, а также овердрафты, отключенные сегодня принудительно
        stmt = (
            sa_select(OverdraftsHistoryOrm)
            .options(
                joinedload(OverdraftsHistoryOrm.balance)
                .joinedload(BalanceOrm.company)
            )
            .where(or_(
                OverdraftsHistoryOrm.end_date.is_(null()),
                and_(
                    OverdraftsHistoryOrm.end_date > self.today - timedelta(days=7),
                    OverdraftsHistoryOrm.overdue
                )
            ))
        )
        overdrafts = await self.select_all(stmt)
        for overdraft in overdrafts:
            if not overdraft.end_date:
                overdraft_delete_date = overdraft.begin_date + timedelta(days=overdraft.days + 1)
                overdraft.end_date = overdraft_delete_date

        report = OverdraftsReport()

        # Отправляем отчет для СБ
        file_for_security_dptmt = report.make_excel(overdrafts)
        file_name = f"Отчет_овердрафты_{date.strftime(datetime.now(tz=TZ), "%Y_%m_%d__%H_%M")}.xlsx"
        self.send_mail(
            recipients=OVERDRAFTS_MAIL_TO,
            subject="ННК отчет: овердрафты",
            text="Отчет",
            files={file_name: file_for_security_dptmt})

    @staticmethod
    def send_mail(recipients: List[str], subject: str, text: str, files: Dict[str, bytes] | None = None) \
            -> None:
        if not files:
            files = {}

        msg = MIMEMultipart()
        msg['From'] = MAIL_FROM
        msg['To'] = ", ".join(recipients)
        msg['Date'] = formatdate(localtime=True)
        msg['Subject'] = subject
        msg.attach(MIMEText(text))

        for file_name, file_content in files.items():
            part = MIMEBase('application', "octet-stream")
            part.set_payload(file_content)
            encoders.encode_base64(part)
            part.add_header('content-disposition', 'attachment', filename=('utf-8', '', file_name))
            msg.attach(part)

        smtp = smtplib.SMTP(MAIL_SERVER, MAIL_PORT)
        # smtp.set_debuglevel(1)
        smtp.starttls()
        smtp.login(MAIL_USER, MAIL_PASSWORD)
        smtp.sendmail(MAIL_FROM, recipients, msg.as_string())
        smtp.quit()
