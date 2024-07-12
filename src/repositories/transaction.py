from datetime import date
from typing import List

from sqlalchemy import select as sa_select, desc
from sqlalchemy.orm import joinedload, load_only

from src.database import models
from src.repositories.base import BaseRepository
from src.utils import enums
from src.utils.exceptions import ForbiddenException

import sqlparse


class TransactionRepository(BaseRepository):
    async def get_transactions(self, start_date: date, end_date: date) -> List[models.Transaction]:
        # Суперадмин ПроАВТО имеет полные права.
        # Менеджер ПроАВТО может получать информацию только по своим организациям.
        # Администратор и логист компании могут получать информацию только по своей организации.
        # Водитель может получать только транзакции по своим картам.
        # Состав списка зависит от роли пользователя.
        stmt = (
            sa_select(models.Transaction)
            .options(
                load_only(
                    models.Transaction.id,
                    models.Transaction.date_time,
                    models.Transaction.date_time_load,
                    models.Transaction.is_debit,
                    models.Transaction.azs_code,
                    models.Transaction.azs_address,
                    models.Transaction.fuel_volume,
                    models.Transaction.price,
                    models.Transaction.transaction_sum,
                    models.Transaction.discount_sum,
                    models.Transaction.fee_percent,
                    models.Transaction.fee_sum,
                    models.Transaction.total_sum,
                    models.Transaction.card_balance,
                    models.Transaction.company_balance,
                    models.Transaction.comments
                )
            )
            .options(
                joinedload(models.Transaction.card)
                .load_only(models.Card.id, models.Card.card_number, models.Card.is_active)
            )
            .options(
                joinedload(models.Transaction.system)
                .load_only(models.System.id, models.System.full_name)
            )
            .options(
                joinedload(models.Transaction.outer_goods)
                .load_only(models.OuterGoods.id, models.OuterGoods.name)
                .joinedload(models.OuterGoods.inner_goods)
            )
            .options(
                joinedload(models.Transaction.tariff)
                .load_only(models.Tariff.id, models.Tariff.name)
            )
            .options(
                joinedload(models.Transaction.company)
                .load_only()
                .joinedload(models.Balance.company)
                .load_only(models.Company.id, models.Company.name, models.Company.inn)
            )
            .where(models.Transaction.date_time >= start_date)
            .where(models.Transaction.date_time < end_date)
            .order_by(models.Transaction.date_time.desc())
        )

        if self.user.role.name == enums.Role.CARGO_SUPER_ADMIN.name:
            pass

        elif self.user.role.name == enums.Role.CARGO_MANAGER.name:
            stmt = stmt.where(models.Transaction.company_id.in_(self.user.company_ids_subquery()))

        elif self.user.role.name in [enums.Role.COMPANY_ADMIN.name, enums.Role.COMPANY_LOGIST.name]:
            stmt = stmt.where(models.Transaction.company_id == self.user.company_id)

        elif self.user.role.name == enums.Role.COMPANY_DRIVER.name:
            stmt = stmt.where(models.Transaction.company_id == self.user.company_id)
            stmt = stmt.where(models.Card.belongs_to_driver_id == self.user.id)

        else:
            raise ForbiddenException()

        transactions = await self.select_all(stmt)
        return transactions

    async def get_last_transaction(self, company_id: str) -> models.Transaction:
        stmt = (
            sa_select(models.Transaction)
            .where(models.Transaction.company_id == company_id)
            .order_by(models.Transaction.date_time.desc())
            .limit(1)
        )
        last_transaction = await self.select_first(stmt)
        return last_transaction

    async def create_corrective_transaction(self, company_id: str, debit: bool, delta_sum: float) -> None:
        # Получаем последнюю транзакцию этой организации
        last_transaction = await self.get_last_transaction(company_id)
        
        # Получаем текущий баланс организации
        current_balance = last_transaction.company_balance if last_transaction else 0

        # Формируем корректирующую транзакцию
        if debit:
            delta_sum = -delta_sum
            
        corrective_transaction = {
            "is_debit": debit,
            "company_id": company_id,
            "transaction_sum": delta_sum,
            "total_sum": delta_sum,
            "company_balance": current_balance + delta_sum,
        }
        corrective_transaction = await self.insert(models.Transaction, **corrective_transaction)

        # Получаем организацию
        stmt = sa_select(models.Company).where(models.Company.id == company_id)
        company = await self.select_first(stmt)

        # Обновляем текущий баланс организации
        update_data = {
            'balance': corrective_transaction.company_balance,
        }
        await self.update_object(company, update_data)
