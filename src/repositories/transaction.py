from datetime import datetime, timedelta
from typing import List, Dict

from sqlalchemy import select as sa_select, and_, func, update as sa_update
from sqlalchemy.orm import joinedload, load_only, aliased

from src.config import TZ
from src.database.model.card import CardOrm
from src.database.model.models import (Transaction as TransactionOrm, System as SystemOrm, OuterGoods as OuterGoodsOrm,
                                       Tariff as TariffOrm, BalanceSystemTariff as BalanceSystemTariffOrm,
                                       CardSystem as CardSystemOrm, BalanceTariffHistory as BalanceTariffHistoryOrm)
from src.database.model.balance import BalanceOrm
from src.database.model.company import CompanyOrm
from src.repositories.base import BaseRepository
from src.utils import enums
from src.utils.enums import TransactionType
from src.utils.exceptions import ForbiddenException


class TransactionRepository(BaseRepository):

    async def get_transactions(self, company_id: str | None, from_dt: datetime, to_dt: datetime) \
            -> List[TransactionOrm]:
        # Суперадмин ПроАВТО имеет полные права.
        # Менеджер ПроАВТО может получать информацию только по своим организациям.
        # Администратор и логист компании могут получать информацию только по своей организации.
        # Водитель может получать только транзакции по своим картам.
        # Состав списка зависит от роли пользователя.
        transaction_table = aliased(TransactionOrm, name="transaction_table")
        balance_table = aliased(BalanceOrm, name="balance_table")
        base_subquery = (
            sa_select(transaction_table.id)
            .where(transaction_table.date_time >= from_dt)
            .where(transaction_table.date_time < to_dt)
        )

        if company_id:
            base_subquery = (
                base_subquery
                .where(balance_table.id == transaction_table.balance_id)
                .where(balance_table.company_id == company_id)
            )

        if self.user.role.name == enums.Role.CARGO_SUPER_ADMIN.name:
            pass

        elif self.user.role.name == enums.Role.CARGO_MANAGER.name:
            balance_table2 = aliased(BalanceOrm, name="balance_table2")
            company_ids_subquery = self.user.company_ids_subquery()
            base_subquery = (
                base_subquery
                .join(balance_table2, balance_table2.id == transaction_table.balance_id)
                .join(company_ids_subquery, company_ids_subquery.c.id == balance_table2.company_id)
            )

        elif self.user.role.name in [enums.Role.COMPANY_ADMIN.name, enums.Role.COMPANY_LOGIST.name]:
            balance_table2 = aliased(BalanceOrm, name="balance_table2")
            base_subquery = (
                base_subquery
                .join(balance_table2, and_(
                    balance_table2.id == transaction_table.balance_id,
                    balance_table2.company_id == self.user.company_id
                ))
            )

        elif self.user.role.name == enums.Role.COMPANY_DRIVER.name:
            balance_table2 = aliased(BalanceOrm, name="balance_table2")
            card_table = aliased(CardOrm, name="card_table")
            base_subquery = (
                base_subquery
                .join(balance_table2, and_(
                    balance_table2.id == transaction_table.balance_id,
                    balance_table2.company_id == self.user.company_id
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
            .order_by(TransactionOrm.date_time_load.desc())
        )

        # self.statement(stmt)
        transactions = await self.select_all(stmt)
        return transactions

    async def get_last_transaction(self, balance_id: str) -> TransactionOrm:
        stmt = (
            sa_select(TransactionOrm)
            .where(TransactionOrm.balance_id == balance_id)
            .order_by(TransactionOrm.date_time_load.desc())
            .limit(1)
        )
        last_transaction = await self.select_first(stmt)
        return last_transaction

    async def create_corrective_transaction(self, balance: BalanceOrm, transaction_type: TransactionType,
                                            delta_sum: float) -> None:
        # Получаем последнюю транзакцию этой организации
        last_transaction = await self.get_last_transaction(balance.id)
        previous_balance_sum = last_transaction.company_balance if last_transaction else balance.balance

        # Формируем корректирующую транзакцию
        if transaction_type == TransactionType.DECREASE:
            delta_sum = -delta_sum

        now = datetime.now(tz=TZ)
        corrective_transaction = {
            "date_time": now,
            "date_time_load": now,
            "transaction_type": transaction_type,
            "balance_id": balance.id,
            "transaction_sum": delta_sum,
            "total_sum": delta_sum,
            "company_balance": previous_balance_sum + delta_sum,
        }
        corrective_transaction = await self.insert(TransactionOrm, **corrective_transaction)

        # Обновляем сумму на балансе
        update_data = {'balance': corrective_transaction.company_balance}
        await self.update_object(balance, update_data)

    async def get_recent_system_transactions(self, system_id: str, transaction_days: int) \
            -> List[TransactionOrm]:
        start_date = datetime.now(tz=TZ).date() - timedelta(days=transaction_days)
        stmt = (
            sa_select(TransactionOrm)
            .options(
                joinedload(TransactionOrm.card),
                joinedload(TransactionOrm.company),
                joinedload(TransactionOrm.outer_goods),
                joinedload(TransactionOrm.tariff)
            )
            .where(TransactionOrm.date_time >= start_date)
            .where(TransactionOrm.system_id == system_id)
            .outerjoin(TransactionOrm.card)
            .order_by(CardOrm.card_number, TransactionOrm.date_time)
        )
        transactions = await self.select_all(stmt)

        # От систем транзакции приходят с указанием времени в формате YYYY-MM-DD HH:MM:SS
        # Обрезаем микросекунды, чтобы можно было сравнивать по времени локальные транзакции с
        # полученными от систем
        for tr in transactions:
            tr.date_time.replace(microsecond=0)

        return transactions

    async def renew_cards_date_last_use(self) -> None:
        date_last_use_subquery = (
            sa_select(func.max(TransactionOrm.date_time))
            .where(TransactionOrm.card_id == CardOrm.id)
            .scalar_subquery()
        )
        stmt = sa_update(CardOrm).values(date_last_use=date_last_use_subquery)
        await self.session.execute(stmt)
        await self.session.commit()

    async def get_balance_system_tariff_list(self, system_id: str) -> List[BalanceSystemTariffOrm]:
        bst = aliased(BalanceSystemTariffOrm, name="bst")
        stmt = (
            sa_select(bst)
            .options(
                joinedload(bst.tariff)
                .load_only(TariffOrm.id, TariffOrm.fee_percent)
            )
            .where(bst.system_id == system_id)
        )
        balance_system_tariff_list = await self.select_all(stmt)
        return balance_system_tariff_list

    async def get_tariffs_history(self, system_id: str) -> List[BalanceTariffHistoryOrm]:
        bth = aliased(BalanceTariffHistoryOrm, name="bth")
        stmt = (
            sa_select(bth)
            .options(
                joinedload(bth.tariff)
                .load_only(TariffOrm.id, TariffOrm.fee_percent)
            )
            .where(bth.system_id == system_id)
        )
        tariffs_history = await self.select_all(stmt)
        return tariffs_history

    async def get_balance_card_relations(self, card_numbers: List[str], system_id: str) -> Dict[str, str]:
        stmt = (
            sa_select(CardOrm.card_number, BalanceOrm.id)
            .select_from(BalanceSystemTariffOrm, BalanceOrm, CompanyOrm, CardOrm, CardSystemOrm)
            .where(CardOrm.card_number.in_(card_numbers))
            .where(CardSystemOrm.card_id == CardOrm.id)
            .where(CardSystemOrm.system_id == system_id)
            .where(BalanceSystemTariffOrm.system_id == system_id)
            .where(BalanceOrm.id == BalanceSystemTariffOrm.balance_id)
            .where(CompanyOrm.id == BalanceOrm.company_id)
            .where(CardOrm.company_id == CompanyOrm.id)
        )
        dataset = await self.select_all(stmt, scalars=False)
        balance_card_relations = {data[0]: data[1] for data in dataset}
        return balance_card_relations

    async def get_outer_goods_list(self, system_id: str) -> List[OuterGoodsOrm]:
        stmt = sa_select(OuterGoodsOrm).where(OuterGoodsOrm.system_id == system_id)
        outer_goods = await self.select_all(stmt)
        return outer_goods
