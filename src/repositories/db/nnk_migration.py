from typing import Dict, Any

import random
from datetime import datetime, date

from src.repositories.base import BaseRepository
from src.database import models
from src.utils import enums

from sqlalchemy import select as sa_select


class NNKMigration(BaseRepository):
    system_ids = None
    balance_ids = None
    card_ids = None
    tariff_ids = None
    company_ids = None
    goods_ids = None


    async def _set_system_ids(self) -> None:
        system_ids = await self.select_all(
            sa_select(models.System.master_db_id, models.System.id).where(models.System.master_db_id != None),
            scalars=False
        )
        self.system_ids = {item[0]: item[1] for item in system_ids}

    async def _set_balance_ids(self) -> None:
        balance_ids = await self.select_all(
            sa_select(models.Company.master_db_id, models.Balance.id)
            .where(models.Company.master_db_id != None)
            .where(models.Company.id == models.Balance.company_id),
            scalars=False
        )
        self.balance_ids = {item[0]: item[1] for item in balance_ids}

    async def _set_card_ids(self) -> None:
        card_numbers_related_to_card_ids = await self.select_all(
            sa_select(models.Card.card_number, models.Card.id),
            scalars=False
        )
        self.card_ids = {item[0]: item[1] for item in card_numbers_related_to_card_ids}

    async def _set_company_ids(self) -> None:
        company_ids = await self.select_all(
            sa_select(models.Company.master_db_id, models.Company.id).where(models.Company.master_db_id != None),
            scalars=False
        )
        self.company_ids = {item[0]: item[1] for item in company_ids}

    async def _set_tariff_ids(self) -> None:
        tariff_ids = await self.select_all(
            sa_select(models.Tariff.master_db_id, models.Tariff.id).where(models.Tariff.master_db_id != None),
            scalars=False
        )
        self.tariff_ids = {item[0]: item[1] for item in tariff_ids}

    async def _set_goods_ids(self) -> None:
        goods = await self.select_all(
            sa_select(models.InnerGoods.name, models.OuterGoods.id)
            .where(models.OuterGoods.inner_goods_id == models.InnerGoods.id),
            scalars=False
        )
        self.goods_ids = {item[0]: item[1] for item in goods}

    async def import_systems(self, systems: list[Dict[str, Any]]) -> None:
        dataset = [
            dict(
                master_db_id=system['id'],
                full_name=system['full_name'],
                short_name=system['short_name'],
                transaction_days=system['transaction_days'],
            ) for system in systems
        ]
        await self.bulk_insert_or_update(models.System, dataset, 'full_name')
        await self._set_system_ids()

    async def import_tariffs(self, tariffs: list[Dict[str, Any]]) -> None:
        dataset = [
            dict(
                master_db_id=tariff['id'],
                name=tariff['title'],
                fee_percent=tariff['service_online'],
            ) for tariff in tariffs
        ]
        await self.bulk_insert_or_update(models.Tariff, dataset, 'name')
        await self._set_tariff_ids()

    async def import_companies(self, companies: list[Dict[str, Any]]) -> None:
        # Создаем записи в таблице company
        dataset = [
            dict(
                master_db_id=company['id'],
                name=company['name'],
                date_add=company['date_add'],
                personal_account=('000000' + str(random.randint(1, 9999999)))[-7:],
                inn=company['inn']
            ) for company in companies
        ]
        await self.bulk_insert_or_update(models.Company, dataset)
        await self._set_company_ids()

    async def import_balances(self, companies: list[Dict[str, Any]]) -> None:
        # Создаем записи в таблице balance
        dataset = [
            dict(
                company_id=self.company_ids[company['id']],
                scheme=enums.ContractScheme.OVERBOUGHT.name,
                balance=company['amount'],
                min_balance=company['min_balance'],
                min_balance_period_end_date=None if company['min_balance_date_to'] == '0000-00-00 00:00:00' else
                company['min_balance_date_to'],
                min_balance_on_period=company['min_balance_period'],
            ) for company in companies
        ]
        await self.bulk_insert_or_update(models.Balance, dataset)
        await self._set_balance_ids()

    """
    async def sync_companies(self, companies: list[Dict[str, Any]]) -> int:
        # Получаем список идентификаторов, указывающих на организации из БД основной площадки
        stmt = sa_select(models.Company.master_db_id)
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
            await self.bulk_insert_or_update(models.Company, dataset)

        return len(dataset)
    """

    async def import_cars(self, cars: list[Dict[str, Any]]) -> None:
        dataset = [
            dict(
                master_db_id=car['id'],
                reg_number=car['car_number'],
                company_id=self.company_ids[car['company_id']],
            ) for car in cars
        ]
        await self.bulk_insert_or_update(models.Car, dataset)

    async def import_cards(self, cards: list[Dict[str, Any]]) -> None:
        # Тип карты по умолчанию для вновь импортируемых карт
        plastic_card_type = await self.insert_or_update(models.CardType, 'name', name="Пластиковая карта")

        # Номера карт в привязке к типам (для существующих карт)
        card_numbers_related_to_card_type_ids = await self.select_all(
            sa_select(models.Card.card_number, models.Card.card_type_id),
            scalars=False
        )
        card_numbers_related_to_card_type_ids = {
            item[0]: item[1] for item in card_numbers_related_to_card_type_ids
        }

        # Автомобиль. Сопоставление id записи на боевом сервере с id на новом сервере.
        car_ids = await self.select_all(
            sa_select(models.Car.master_db_id, models.Car.id).where(models.Car.master_db_id != None),
            scalars=False
        )
        car_ids = {item[0]: item[1] for item in car_ids}

        dataset = [
            dict(
                card_type_id=card_numbers_related_to_card_type_ids.get(card['card_num'], plastic_card_type.id),
                card_number=card['card_num'],
                belongs_to_car_id=car_ids[card['car_id']] if card['car_id'] else None,
                is_active=card['state'],
                manual_lock=card['manual_lock'],
            ) for card in cards
        ]
        await self.bulk_insert_or_update(models.Card, dataset, 'card_number')
        await self._set_card_ids()

    async def import_card_bindings(self, cards: list[Dict[str, Any]]) -> None:
        # Создаем записи в таблице card_binding
        dataset = [
            dict(
                card_id=self.card_ids[str(card['card_num'])],
                system_id=self.system_ids[card['system_id']],
                balance_id=self.balance_ids[card['company_id']] if card['company_id'] else None
            ) for card in cards if card['system_id']
        ]
        await self.bulk_insert_or_update(models.CardBinding, dataset)

    async def import_tariffs_history(self, companies: list[Dict[str, Any]]) -> None:
        # Создаем записи в таблице tariff_history
        # Для всех организаций привязываем текущий тариф к балансу ННК с открытой датой.
        # Для остальных систем выполняем привязку с указанием даты прекращения действия.

        # ННК
        nnk_system = await self.select_first(sa_select(models.System).where(
            models.System.full_name == "АО «ННК-Хабаровскнефтепродукт»")
        )
        dataset = [
            dict(
                tariff_id=self.tariff_ids[company['tariff_id']],
                balance_id=self.balance_ids[company['id']],
                system_id=nnk_system.id,
                start_date=datetime.fromisoformat(company['date_add']).date(),
                end_date=None,
                current=True,
            ) for company in companies
        ]
        await self.bulk_insert_or_update(models.TariffHistory, dataset)

        # Остальные системы
        systems = await self.select_all(sa_select(models.System))
        for system in systems:
            if system.id != nnk_system.id:
                dataset = [
                    dict(
                        tariff_id=self.tariff_ids[company['tariff_id']],
                        balance_id=self.balance_ids[company['id']],
                        system_id=system.id,
                        start_date=datetime.fromisoformat(company['date_add']).date(),
                        end_date=date.today(),
                        current=False,
                    ) for company in companies
                ]
                await self.bulk_insert_or_update(models.TariffHistory, dataset)

    async def import_inner_goods(self, goods: list[Dict[str, Any]]) -> None:
        dataset = [{'name': good['inner_goods']} for good in goods if good['inner_goods']]
        await self.bulk_insert_or_update(models.InnerGoods, dataset)

    async def import_outer_goods(self, goods: list[Dict[str, Any]]) -> None:
        # Пример входной строки goods:
        # {
        #     "system_id": System.master_db_id,
        #     "outer_goods": OuterGoods.name,
        #     "inner_goods": InnerGoods.name
        # }

        # Наименования товаров в привязке к id
        inner_goods_ids = await self.select_all(
            sa_select(models.InnerGoods.name, models.InnerGoods.id),
            scalars=False
        )
        inner_goods_ids = {item[0]: item[1] for item in inner_goods_ids}

        dataset = [
            dict(
                name=str(good['outer_goods']),
                system_id=self.system_ids[good['system_id']],
                inner_goods_id=inner_goods_ids[good['inner_goods']] if good['inner_goods'] else None,
            ) for good in goods if good['system_id'] in self.system_ids
        ]

        await self.bulk_insert_or_update(models.OuterGoods, dataset)
        await self._set_goods_ids()

    async def import_transactions(self, transactions: list[Dict[str, Any]]) -> None:
        dataset = [
            dict(
                master_db_id=transaction['id'],
                external_id=transaction['id'],
                date_time=datetime.fromisoformat(transaction['date']),
                date_time_load=datetime.fromisoformat(transaction['date_load']),
                is_debit=True if transaction['sum'] < 0 else False,
                card_id=self.card_ids[str(transaction['card_num'])] if transaction['card_num']
                else None,
                balance_id=self.balance_ids[transaction['company_id']] if transaction['company_id'] else None,
                system_id=self.system_ids[transaction['company_id']] if transaction['company_id'] else None,
                azs_code=transaction['azs'],
                azs_address=transaction['address'],
                outer_goods_id=self.goods_ids[transaction['gds']] if transaction['gds'] in self.goods_ids else None,
                fuel_volume=transaction['volume'],
                price=transaction['price'],
                transaction_sum=transaction['sum'],
                tariff_id=None,
                fee_sum=transaction['sum_service'],
                total_sum=transaction['total'],
                company_balance=0,  # После импорта будет выполнен пересчет балансов, поле примет новые значения
                comments=transaction['comment'],
            ) for transaction in transactions
        ]

        await self.bulk_insert_or_update(models.Transaction, dataset)
