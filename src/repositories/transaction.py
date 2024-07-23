from datetime import date
from typing import List

from sqlalchemy import select as sa_select, and_
from sqlalchemy.orm import joinedload, load_only, aliased

from src.database.models import (Transaction as TransactionOrm, Card as CardOrm, System as SystemOrm, 
                                 OuterGoods as OuterGoodsOrm, Tariff as TariffOrm, Company as CompanyOrm,
                                 Balance as BalanceOrm)
from src.repositories.base import BaseRepository
from src.utils import enums
from src.utils.enums import TransactionType
from src.utils.exceptions import ForbiddenException


class TransactionRepository(BaseRepository):
    async def get_transactions(self, start_date: date, end_date: date) -> List[TransactionOrm]:
        # Суперадмин ПроАВТО имеет полные права.
        # Менеджер ПроАВТО может получать информацию только по своим организациям.
        # Администратор и логист компании могут получать информацию только по своей организации.
        # Водитель может получать только транзакции по своим картам.
        # Состав списка зависит от роли пользователя.
        transaction_table = aliased(TransactionOrm, name="transaction_table")
        base_subquery = (
            sa_select(transaction_table.id)
            .where(transaction_table.date_time >= start_date)
            .where(transaction_table.date_time < end_date)
        )

        if self.user.role.name == enums.Role.CARGO_SUPER_ADMIN.name:
            pass

        elif self.user.role.name == enums.Role.CARGO_MANAGER.name:
            balance_table = aliased(BalanceOrm, name="balance_table")
            company_ids_subquery = self.user.company_ids_subquery()
            base_subquery = (
                base_subquery
                .join(balance_table, balance_table.id == transaction_table.balance_id)
                .join(company_ids_subquery, company_ids_subquery.c.id == balance_table.company_id)
            )

        elif self.user.role.name in [enums.Role.COMPANY_ADMIN.name, enums.Role.COMPANY_LOGIST.name]:
            balance_table = aliased(BalanceOrm, name="balance_table")
            base_subquery = (
                base_subquery
                .join(balance_table, and_(
                    balance_table.id == transaction_table.balance_id,
                    balance_table.company_id == self.user.company_id
                ))
            )

        elif self.user.role.name == enums.Role.COMPANY_DRIVER.name:
            balance_table = aliased(BalanceOrm, name="balance_table")
            card_table = aliased(CardOrm, name="card_table")
            base_subquery = (
                base_subquery
                .join(balance_table, and_(
                    balance_table.id == transaction_table.balance_id,
                    balance_table.company_id == self.user.company_id
                ))
                .join(card_table, and_(
                    card_table.id == transaction_table.card_id,
                    card_table.belongs_to_driver_id == self.user.id
                ))
            )

        else:
            raise ForbiddenException()

        base_subquery = base_subquery.subquery("helper_base")
        stmt = (
            sa_select(TransactionOrm)
            .options(
                load_only(
                    TransactionOrm.id,
                    TransactionOrm.date_time,
                    TransactionOrm.date_time_load,
                    TransactionOrm.transaction_type,
                    TransactionOrm.azs_code,
                    TransactionOrm.azs_address,
                    TransactionOrm.fuel_volume,
                    TransactionOrm.price,
                    TransactionOrm.transaction_sum,
                    TransactionOrm.discount_sum,
                    TransactionOrm.fee_percent,
                    TransactionOrm.fee_sum,
                    TransactionOrm.total_sum,
                    TransactionOrm.card_balance,
                    TransactionOrm.company_balance,
                    TransactionOrm.comments
                )
            )
            .options(
                joinedload(TransactionOrm.card)
                .load_only(CardOrm.id, CardOrm.card_number, CardOrm.is_active)
            )
            .options(
                joinedload(TransactionOrm.system)
                .load_only(SystemOrm.id, SystemOrm.full_name)
            )
            .options(
                joinedload(TransactionOrm.outer_goods)
                .load_only(OuterGoodsOrm.id, OuterGoodsOrm.name)
                .joinedload(OuterGoodsOrm.inner_goods)
            )
            .options(
                joinedload(TransactionOrm.tariff)
                .load_only(TariffOrm.id, TariffOrm.name)
            )
            .options(
                joinedload(TransactionOrm.company)
                .load_only()
                .joinedload(BalanceOrm.company)
                .load_only(CompanyOrm.id, CompanyOrm.name, CompanyOrm.inn)
            )
            .select_from(base_subquery, TransactionOrm)
            .where(TransactionOrm.id == base_subquery.c.id)
            .order_by(TransactionOrm.date_time.desc())
        )

        # self.statement(stmt)
        transactions = await self.select_all(stmt)
        return transactions

    async def get_last_transaction(self, balance_id: str) -> TransactionOrm:
        stmt = (
            sa_select(TransactionOrm)
            .where(TransactionOrm.balance_id == balance_id)
            .order_by(TransactionOrm.date_time.desc())
            .limit(1)
        )
        last_transaction = await self.select_first(stmt)
        return last_transaction

    async def create_corrective_transaction(self, balance: BalanceOrm, debit: bool, delta_sum: float) -> None:
        # Получаем последнюю транзакцию этой организации
        last_transaction = await self.get_last_transaction(balance.id)

        # Формируем корректирующую транзакцию
        if debit:
            delta_sum = -delta_sum
            
        corrective_transaction = {
            "transaction_type": TransactionType.PURCHASE if debit else TransactionType.REFUND,
            "balance_id": balance.id,
            "transaction_sum": delta_sum,
            "total_sum": delta_sum,
            "company_balance": last_transaction.company_balance + delta_sum,
        }
        corrective_transaction = await self.insert(TransactionOrm, **corrective_transaction)

        # Обновляем сумму на балансе
        update_data = {'balance': corrective_transaction.company_balance}
        await self.update_object(balance, update_data)
