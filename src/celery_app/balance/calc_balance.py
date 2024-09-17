import os
from datetime import datetime
from typing import List, Dict, Any

from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.celery_app.exceptions import CeleryError
from src.celery_app.irrelevant_balances import IrrelevantBalances
from src.celery_app.transaction_helper import TransactionHelper
from src.config import TZ
from src.database.models.balance import BalanceOrm
from src.database.models.transaction import TransactionOrm
from src.repositories.base import BaseRepository
from src.repositories.system import SystemRepository
from src.repositories.transaction import TransactionRepository
from src.utils.common import banking_round
from src.utils.enums import ContractScheme
from src.utils.loggers import get_logger


class CalcBalances(BaseRepository):

    def __init__(self, session: AsyncSession):
        super().__init__(session=session, user=None)
        self.logger = get_logger(name="CALC_BALANCES", filename="celery.log")
        self.helper = TransactionHelper(session=session, logger=self.logger)

    async def calculate(self, irrelevant_balances: IrrelevantBalances) -> Dict[str, List[str]]:
        balances_dataset = []
        for balance_id, from_date_time in irrelevant_balances['irrelevant_balances'].items():
            # Вычисляем и устанавливаем балансы в истории транзакций
            company_balance = await self.calculate_transaction_balances(balance_id, from_date_time)
            balances_dataset.append({"id": balance_id, "balance": company_balance})

        # Обновляем текущие балансы
        self.logger.info('Обновляю текущие значения балансов')
        await self.bulk_update(BalanceOrm, balances_dataset)

        # Вычисляем каким организациям нужно заблокировать карты, а каким разблокировать
        balance_ids_to_change_card_states = await self.calc_card_states()

        return balance_ids_to_change_card_states

    async def get_initial_transaction(self, balance_id: str, from_date_time: datetime) -> TransactionOrm:
        stmt = (
            sa_select(TransactionOrm)
            .where(TransactionOrm.balance_id == balance_id)
            .where(TransactionOrm.date_time_load < from_date_time)
            .order_by(TransactionOrm.date_time_load.desc())
            .limit(1)
        )
        # self.statement(stmt)
        transaction = await self.select_first(stmt)
        return transaction

    async def get_transactions_to_recalculate(self, balance_id: str, from_date_time: datetime) -> List[TransactionOrm]:
        stmt = (
            sa_select(TransactionOrm)
            .options(
                joinedload(TransactionOrm.balance)
                .joinedload(BalanceOrm.company)
            )
            .where(TransactionOrm.balance_id == balance_id)
            .where(TransactionOrm.date_time_load >= from_date_time)
            .order_by(TransactionOrm.date_time_load)
        )
        transactions = await self.select_all(stmt)
        return transactions

    async def calculate_transaction_balances(self, balance_id: str, from_date_time: datetime) -> float:
        # Получаем транзакцию компании, которая предшествует указанному времени
        initial_transaction = await self.get_initial_transaction(balance_id, from_date_time)

        # Получаем все транзакции компании по указанному балансу, начиная с указанного времени
        transactions_to_recalculate = await self.get_transactions_to_recalculate(balance_id, from_date_time)

        # Пересчитываем балансы
        previous_transaction = initial_transaction
        for transaction in transactions_to_recalculate:
            transaction.company_balance = previous_transaction.company_balance + transaction.total_sum \
                if previous_transaction else transaction.total_sum

            previous_transaction = transaction

        # Сохраняем в БД
        dataset = []
        for transaction in transactions_to_recalculate:
            dataset.append({
                'id': transaction.id,
                'company_balance_after': transaction.company_balance,
            })
            await self.bulk_update(TransactionOrm, dataset)

        last_balance = previous_transaction.company_balance if previous_transaction else 0
        return last_balance

    async def calc_card_states(self) -> Dict[str, List[str]]:
        # Получаем все перекупные балансы
        stmt = (
            sa_select(BalanceOrm)
            .options(
                joinedload(BalanceOrm.company)
            )
            .where(BalanceOrm.scheme == ContractScheme.OVERBOUGHT)
        )
        balances = await self.select_all(stmt)

        # Анализируем настройки организации и текущий баланс, делаем заключение о том,
        # какое состояние карт у этой организации должно быть
        balance_ids_to_block_cards = set()
        balance_ids_to_activate_cards = set()
        for balance in balances:
            # Получаем размер овердрафта
            overdraft_sum = balance.company.overdraft_sum if balance.company.overdraft_on else 0
            if overdraft_sum > 0:
                overdraft_sum = -overdraft_sum

            # Получаем порог баланса, ниже которого требуется блокировка карт
            boundary = balance.company.min_balance + overdraft_sum

            if balance.balance < boundary:
                # Делаем пометку о том, что у этой организации карты должны находиться в заблокированном состоянии
                balance_ids_to_block_cards.add(balance.id)

            else:
                # Делаем пометку о том, что у этой организации карты должны находиться в разблокированном состоянии
                balance_ids_to_activate_cards.add(balance.id)

        balance_ids_to_change_card_states = dict(
            to_block = list(balance_ids_to_block_cards),
            to_activate = list(balance_ids_to_activate_cards)
        )
        return balance_ids_to_change_card_states

    async def recalculate_transactions(self, from_date_time: datetime, personal_accounts: List[str] | None) \
            -> Dict[str, Any]:
        # Получаем транзакции с указанного времени
        transaction_repository = TransactionRepository(session=self.session)
        transactions = await transaction_repository.get_transactions_from_date_time(
            from_date_time=from_date_time,
            personal_accounts=personal_accounts
        )

        # Получаем историю карт
        system_repository = SystemRepository(session=self.session)
        systems = await system_repository.get_systems()
        balance_ids = {transaction.balance_id for transaction in transactions}
        systems_dict = {}
        for system in systems:
            irrelevant_balances = IrrelevantBalances(system_id=system.id)
            for balance_id in balance_ids:
                irrelevant_balances.add(balance_id, from_date_time)
            systems_dict[system.id] = {
                "system_name": system.short_name,
                "irrelevant_balances": irrelevant_balances
            }

        def process_delta_sum(personal_account_: str, delta_sum_: float, system_id_: str):
            if personal_account_ in systems_dict[system_id_]["irrelevant_balances"].total_sum_deltas:
                systems_dict[system_id_]["irrelevant_balances"].total_sum_deltas[personal_account_] += delta_sum_
            else:
                systems_dict[system_id_]["irrelevant_balances"].total_sum_deltas[personal_account_] = delta_sum_

        transaction_dataset = []
        for transaction in transactions:
            # Пропускаем транзакции, сгенерированные не в системе поставщика
            if not transaction.system_id:
                continue

            # Получаем карту
            card = await self.helper.get_card(card_id=transaction.card_id)
            company = await self.helper.get_card_company_on_time(card, transaction.date_time)
            azs = await self.helper.get_azs(azs_external_id=transaction.azs_code)
            if not azs:
                raise CeleryError(f"Не удалось определить АЗС по транзакции от {transaction.date_time}. "
                                  f"AZS_EXTERNAL_ID: {transaction.azs_code} | "
                                  f"SYSTEM: {systems_dict[transaction.system_id]['system_name']}")

            inner_group = transaction.outer_goods.outer_group.inner_group \
                if transaction.outer_goods.outer_group_id else None

            tariff = await self.helper.get_company_tariff_on_transaction_time(
                company=company,
                transaction_time=transaction.date_time,
                inner_group=inner_group,
                azs=azs,
                system_id=str(transaction.system_id)
            )
            if not tariff:
                raise CeleryError(f"Не удалось определить тариф для транзакции {transaction}")

            discount_fee_sum = banking_round(transaction.transaction_sum * tariff.discount_fee / 100)
            total_sum = banking_round(transaction.transaction_sum + discount_fee_sum)
            if transaction.total_sum != total_sum:
                discount_sum = discount_fee_sum if tariff.discount_fee < 0 else 0
                fee_sum = discount_fee_sum if tariff.discount_fee > 0 else 0
                transaction_dataset.append(
                    {
                        "id": transaction.id,
                        "tariff_new_id": tariff.id,
                        "discount_sum": discount_sum,
                        "fee_sum": fee_sum,
                        "total_sum": total_sum,
                        "company_balance": 0,
                        "comment": f"Пересчитаны транзакции: {datetime.now(tz=TZ).replace(microsecond=0).isoformat()}"
                    }
                )

                # Вычисляем дельту изменения суммы баланса - понадобится позже для правильного
                # выставления лимита на группу карт
                delta_sum = total_sum - transaction.total_sum
                process_delta_sum(
                    personal_account_=company.personal_account,
                    delta_sum_=delta_sum,
                    system_id_=str(transaction.system_id)
                )
                # if systems_dict[transaction.system_id]['system_name'] != System.OPS.value:
                self.logger.info(
                    f"{os.linesep}--------------"
                    f"{os.linesep}Пересчитана транзакция {company.name} от {transaction.date_time} "
                    f"на итоговую сумму               {transaction.total_sum}. "
                    f"{os.linesep}Система:            {systems_dict[transaction.system_id]['system_name']} "
                    f"{os.linesep}transaction_sum:    {transaction.transaction_sum} "
                    f"{os.linesep}discount_sum ДО:    {transaction.discount_sum} "
                    f"{os.linesep}discount_sum ПОСЛЕ: {discount_sum} "
                    f"{os.linesep}fee_sum ДО:         {transaction.fee_sum} "
                    f"{os.linesep}fee_sum ПОСЛЕ:      {fee_sum} "
                    f"{os.linesep}total_sum ДО:       {transaction.total_sum} "
                    f"{os.linesep}total_sum ПОСЛЕ:    {total_sum} "
                    f"{os.linesep}Тариф ДО:           {transaction.tariff_new_id} "
                    f"{os.linesep}Тариф ПОСЛЕ:        {tariff.id} "
                    f"{os.linesep}Тариф ПОСЛЕ (%):    {tariff.discount_fee} "
                    f"{os.linesep}"
                )

        await self.bulk_update(TransactionOrm, transaction_dataset)
        self.logger.info("Пересчет транзакций завершен")
        return systems_dict
