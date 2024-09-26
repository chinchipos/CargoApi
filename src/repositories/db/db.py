from typing import List, Any

from src.database.models.role import RoleOrm
from src.database.models.transaction import TransactionOrm
from src.database.models.balance import BalanceOrm
from src.database.models.card_type import CardTypeOrm
from src.repositories.base import BaseRepository
from src.repositories.db.nnk_migration import NNKMigration
from src.schemas.db import DBInitialSyncSchema
from src.utils.exceptions import DBException
from src.utils import enums

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import select as sa_select, desc


class DBRepository(BaseRepository):

    async def init_roles(self) -> None:
        dataset = [
            {
                'name': role.name,
                'title': role.value['title'],
                'description': role.value['description']
            } for role in enums.Role
        ]
        stmt = pg_insert(RoleOrm).on_conflict_do_nothing()
        try:
            async with self.session.begin():
                await self.session.execute(stmt, dataset)
                await self.session.commit()
        except Exception:
            raise DBException()

    async def init_card_types(self) -> None:
        dataset = [
            {'name': 'Пластиковая карта'},
            {'name': 'Виртуальная карта'}
        ]
        stmt = pg_insert(CardTypeOrm).on_conflict_do_nothing()
        try:
            await self.session.execute(stmt, dataset)
            await self.session.commit()
        except Exception:
            raise DBException()

    async def nnk_initial_sync(self, data: DBInitialSyncSchema) -> None:
        nnk = NNKMigration(self.session, self.user)

        self.logger.info('Импортирую системы')
        await nnk.import_systems(data.systems)

        self.logger.info('Импортирую тарифы')
        await nnk.import_tariffs(data.tariffs)

        self.logger.info('Импортирую организации')
        await nnk.import_companies(data.companies)

        self.logger.info('Импортирую балансы')
        await nnk.import_balances(data.companies)

        self.logger.info('Импортирую автомобили')
        await nnk.import_cars(data.cars)

        self.logger.info('Импортирую топливные карты')
        await nnk.import_cards(data.cards)
        await nnk.bind_cards_with_systems(data.cards)
        await nnk.import_tariffs_history(data.companies)

        self.logger.info('Импортирую товары/услуги')
        await nnk.import_inner_goods(data.goods)
        await nnk.import_outer_goods(data.goods)

        self.logger.info('Импортирую транзакции')
        await nnk.import_transactions(data.transactions)

        self.logger.info('Импортирую пользователей')
        await nnk.import_users(data.users)

    async def get_cargo_superadmin_role(self) -> RoleOrm:
        try:
            stmt = sa_select(RoleOrm).where(RoleOrm.name == enums.Role.CARGO_SUPER_ADMIN.name).limit(1)
            dataset = await self.session.scalars(stmt)
            role = dataset.first()
            return role

        except Exception:
            raise DBException()

    async def get_balances(self) -> List[BalanceOrm]:
        stmt = sa_select(BalanceOrm)
        dataset = await self.select_all(stmt)
        return dataset

    async def get_balance_transactions(self, balance: BalanceOrm) -> List[TransactionOrm]:
        stmt = (
            sa_select(TransactionOrm)
            .where(TransactionOrm.balance_id == balance.id)
            .order_by(desc(TransactionOrm.date_time))
        )
        dataset = await self.select_all(stmt)
        return dataset

    async def get_all_table_records(self, orm_class) -> List[List[Any]]:
        stmt = sa_select(orm_class)
        records = await self.select_all(stmt)
        return records
