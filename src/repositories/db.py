import random
from datetime import datetime
from typing import Dict, Any

from src.database import models
from src.database.models import System, Tariff, Company, Car, CardType, Card, CardSystem, InnerGoods, OuterGoods, \
    Transaction
from src.repositories.base import BaseRepository
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
        stmt = pg_insert(models.Role).on_conflict_do_nothing()
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
        stmt = pg_insert(models.CardType).on_conflict_do_nothing()
        try:
            await self.session.execute(stmt, dataset)
            await self.session.commit()
        except Exception:
            raise DBException()

    async def import_systems(self, systems: list[Dict[str, Any]]) -> None:
        dataset = [
            dict(
                master_db_id=system['id'],
                full_name=system['full_name'],
                short_name=system['short_name'],
                login=system['login'],
                password=system['password'],
                transaction_days=system['transaction_days'],
            ) for system in systems
        ]
        await self.bulk_insert_or_update(System, dataset, 'full_name')

    async def import_tariffs(self, tariffs: list[Dict[str, Any]]) -> None:
        dataset = [
            dict(
                master_db_id=tariff['id'],
                name=tariff['title'],
                fee_percent=tariff['service_online'],
            ) for tariff in tariffs
        ]
        await self.bulk_insert_or_update(Tariff, dataset, 'name')

    async def import_companies(self, companies: list[Dict[str, Any]]) -> None:
        # Тариф. Сопоставление id записи на боевом сервере с наименованием тарифа на новом сервере.
        tariff_ids = await self.select_all(
            sa_select(Tariff.master_db_id, Tariff.id).where(Tariff.master_db_id != None),
            scalars=False
        )
        rate_ids_related_to_tariff_ids = {item[0]: item[1] for item in tariff_ids}

        dataset = [
            dict(
                master_db_id=company['id'],
                name=company['name'],
                date_add=company['date_add'],
                tariff_id=rate_ids_related_to_tariff_ids[company['rate_id']],
                personal_account=('000000' + str(random.randint(1, 9999999)))[-7:],
                inn=company['inn'],
                balance=company['amount'],
                min_balance=company['min_balance'],
                min_balance_period_end_date=None if company['min_balance_date_to'] == '0000-00-00 00:00:00' else
                company['min_balance_date_to'],
                min_balance_on_period=company['min_balance_period'],
            ) for company in companies
        ]
        await self.bulk_insert_or_update(Company, dataset, 'inn')

    async def sync_companies(self, companies: list[Dict[str, Any]]) -> int:
        # Получаем список идентификаторов, указывающих на организации из БД основной площадки
        stmt = sa_select(Company.master_db_id)
        dataset = await self.select_all(stmt, scalars=False)
        excluded_master_db_ids = [row[0] for row in dataset]
        dataset = [
            dict(
                master_db_id=company['id'],
                name=company['name'],
                date_add=company['date_add'],
                tariff_id=None,
                personal_account=('000000' + str(random.randint(1, 9999999)))[-7:],
                inn=company['inn'],
                balance=company['amount'],
                min_balance=company['min_balance'],
                min_balance_period_end_date=None if company['min_balance_date_to'] == '0000-00-00 00:00:00' else
                company['min_balance_date_to'],
                min_balance_on_period=company['min_balance_period'],
            ) for company in companies if company['id'] not in excluded_master_db_ids
        ]
        if dataset:
            await self.bulk_insert_or_update(Company, dataset)

        return len(dataset)

    async def import_cars(self, cars: list[Dict[str, Any]]) -> None:
        # Организация. Сопоставление id записи на боевом сервере с id на новом сервере.
        company_ids = await self.select_all(
            sa_select(Company.master_db_id, Company.id).where(Company.master_db_id != None),
            scalars=False
        )
        company_ids = {item[0]: item[1] for item in company_ids}

        dataset = [
            dict(
                master_db_id=car['id'],
                reg_number=car['car_number'],
                company_id=company_ids[car['company_id']],
            ) for car in cars
        ]
        await self.bulk_insert_or_update(Car, dataset)

    async def import_cards(self, cards: list[Dict[str, Any]]) -> None:
        # Тип карты по умолчанию для вновь импортируемых карт
        plastic_card_type = await self.insert_or_update(CardType, 'name', name="Пластиковая карта")

        # Номера карт в привязке к типам (для существующих карт)
        card_numbers_related_to_card_type_ids = await self.select_all(
            sa_select(Card.card_number, Card.card_type_id),
            scalars=False
        )
        card_numbers_related_to_card_type_ids = {
            item[0]: item[1] for item in card_numbers_related_to_card_type_ids
        }

        # Организация. Сопоставление id записи на боевом сервере с id на новом сервере.
        company_ids = await self.select_all(
            sa_select(Company.master_db_id, Company.id).where(Company.master_db_id != None),
            scalars=False
        )
        company_ids = {item[0]: item[1] for item in company_ids}
        company_ids[0] = None

        # Автомобиль. Сопоставление id записи на боевом сервере с id на новом сервере.
        car_ids = await self.select_all(
            sa_select(Car.master_db_id, Car.id).where(Car.master_db_id != None),
            scalars=False
        )
        car_ids = {item[0]: item[1] for item in car_ids}

        dataset = [
            dict(
                card_type_id=card_numbers_related_to_card_type_ids.get(card['card_num'], plastic_card_type.id),
                card_number=card['card_num'],
                company_id=company_ids[card['company_id']],
                belongs_to_car_id=car_ids[card['car_id']] if card['car_id'] else None,
                is_active=card['state'],
                manual_lock=card['manual_lock'],
            ) for card in cards
        ]
        await self.bulk_insert_or_update(Card, dataset, 'card_number')

    async def import_card_systems(self, cards: list[Dict[str, Any]]) -> None:
        # Номера карт в привязке к id
        card_numbers_related_to_card_ids = await self.select_all(
            sa_select(Card.card_number, Card.id),
            scalars=False
        )
        card_numbers_related_to_card_ids = {item[0]: item[1] for item in card_numbers_related_to_card_ids}

        # Система. Сопоставление id записи на боевом сервере с id на новом сервере.
        system_ids = await self.select_all(
            sa_select(System.master_db_id, System.id).where(System.master_db_id != None),
            scalars=False
        )
        system_ids = {item[0]: item[1] for item in system_ids}

        dataset = [
            dict(
                card_id=card_numbers_related_to_card_ids[str(card['card_num'])],
                system_id=system_ids[card['system_id']],
            ) for card in cards
        ]
        await self.bulk_insert_or_update(CardSystem, dataset)

    async def import_inner_goods(self, goods: list[Dict[str, Any]]) -> None:
        dataset = [{'name': good['inner_goods']} for good in goods if good['inner_goods']]
        await self.bulk_insert_or_update(InnerGoods, dataset)

    async def import_outer_goods(self, goods: list[Dict[str, Any]]) -> None:
        # Пример входной строки goods:
        # {
        #     "system_id": System.master_db_id,
        #     "outer_goods": OuterGoods.name,
        #     "inner_goods": InnerGoods.name
        # }

        # Система. Сопоставление id записи на боевом сервере с id на новом сервере.
        system_ids = await self.select_all(
            sa_select(System.master_db_id, System.id).where(System.master_db_id != None),
            scalars=False
        )
        system_ids = {item[0]: item[1] for item in system_ids}

        # Наименования товаров в привязке к id
        inner_goods_ids = await self.select_all(
            sa_select(InnerGoods.name, InnerGoods.id),
            scalars=False
        )
        inner_goods_ids = {item[0]: item[1] for item in inner_goods_ids}

        dataset = [
            dict(
                name=str(good['outer_goods']),
                system_id=system_ids[good['system_id']],
                inner_goods_id=inner_goods_ids[good['inner_goods']] if good['inner_goods'] else None,
            ) for good in goods if good['system_id'] in system_ids
        ]

        await self.bulk_insert_or_update(OuterGoods, dataset)

    async def import_transactions(self, transactions: list[Dict[str, Any]]) -> None:
        # Система. Сопоставление id записи на боевом сервере с id на новом сервере.
        system_ids = await self.select_all(
            sa_select(System.master_db_id, System.id).where(System.master_db_id != None),
            scalars=False
        )
        system_ids = {item[0]: item[1] for item in system_ids}

        # Номера карт в привязке к id
        card_numbers_related_to_card_ids = await self.select_all(
            sa_select(Card.card_number, Card.id),
            scalars=False
        )
        card_numbers_related_to_card_ids = {item[0]: item[1] for item in card_numbers_related_to_card_ids}

        # Организация. Сопоставление id записи на боевом сервере с id на новом сервере.
        company_ids = await self.select_all(
            sa_select(Company.master_db_id, Company.id).where(Company.master_db_id != None),
            scalars=False
        )
        company_ids = {item[0]: item[1] for item in company_ids}

        # Коды товаров/услуг в привязке к id
        goods = await self.select_all(
            sa_select(InnerGoods.name, OuterGoods.id).where(OuterGoods.inner_goods_id == InnerGoods.id),
            scalars=False
        )
        goods_ids = {item[0]: item[1] for item in goods}

        dataset = [
            dict(
                master_db_id=transaction['id'],
                external_id=transaction['id'],
                date_time=datetime.fromisoformat(transaction['date']),
                date_time_load=datetime.fromisoformat(transaction['date_load']),
                is_debit=True if transaction['sum'] < 0 else False,
                system_id=system_ids[transaction['system_id']] if transaction['system_id'] else None,
                card_id=card_numbers_related_to_card_ids[str(transaction['card_num'])] if transaction['card_num'] else None,
                company_id=company_ids[transaction['company_id']] if transaction['company_id'] else None,
                azs_code=transaction['azs'],
                azs_address=transaction['address'],
                outer_goods_id=goods_ids[transaction['gds']] if transaction['gds'] in goods_ids else None,
                fuel_volume=transaction['volume'],
                price=transaction['price'],
                transaction_sum=transaction['sum'],
                fee_sum=transaction['sum_service'],
                total_sum=transaction['total'],
                company_balance=0,
                comments=transaction['comment'],
            ) for transaction in transactions
        ]

        await self.bulk_insert_or_update(Transaction, dataset)

    async def get_cargo_superadmin_role(self) -> models.Role:
        try:
            stmt = sa_select(models.Role).where(models.Role.name == enums.Role.CARGO_SUPER_ADMIN.name).limit(1)
            dataset = await self.session.scalars(stmt)
            role = dataset.first()
            return role

        except Exception:
            raise DBException()

    async def get_companies(self) -> Any:
        stmt = sa_select(Company)
        dataset = await self.select_all(stmt)
        return dataset

    async def get_company_transactions(self, company: Company) -> Any:
        stmt = (
            sa_select(Transaction)
            .where(Transaction.company_id == company.id)
            .order_by(desc(Transaction.date_time))
        )
        dataset = await self.select_all(stmt)
        return dataset
