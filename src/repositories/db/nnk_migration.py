from typing import Dict, Any

import random
from datetime import datetime

from src.repositories.base import BaseRepository
from src.database import models
from src.utils import enums

from sqlalchemy import select as sa_select


class NNKMigration(BaseRepository):

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

    async def import_tariffs(self, tariffs: list[Dict[str, Any]]) -> None:
        dataset = [
            dict(
                master_db_id=tariff['id'],
                name=tariff['title'],
                fee_percent=tariff['service_online'],
            ) for tariff in tariffs
        ]
        await self.bulk_insert_or_update(models.Tariff, dataset, 'name')

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

    async def import_balances(self, companies: list[Dict[str, Any]]) -> None:
        # Организация. Сопоставление id записи на боевом сервере с id на новом сервере.
        company_ids = await self.select_all(
            sa_select(models.Company.master_db_id, models.Company.id).where(models.Company.master_db_id != None),
            scalars=False
        )
        company_ids = {item[0]: item[1] for item in company_ids}

        # Создаем записи в таблице balance
        dataset = [
            dict(
                company_id=company_ids[company['id']],
                scheme=enums.ContractScheme.OVERBOUGHT.name,
                balance=company['amount'],
                min_balance=company['min_balance'],
                min_balance_period_end_date=None if company['min_balance_date_to'] == '0000-00-00 00:00:00' else
                company['min_balance_date_to'],
                min_balance_on_period=company['min_balance_period'],
            ) for company in companies
        ]
        await self.bulk_insert_or_update(models.Balance, dataset)

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

    async def import_cars(self, cars: list[Dict[str, Any]]) -> None:
        # Организация. Сопоставление id записи на боевом сервере с id на новом сервере.
        company_ids = await self.select_all(
            sa_select(models.Company.master_db_id, models.Company.id).where(models.Company.master_db_id != None),
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

    async def import_contracts(
        self,
        cards:
        list[Dict[str, Any]],
        companies: list[Dict[str, Any]],
        transactions: list[Dict[str, Any]]
    ) -> None:
        # Номера карт в привязке к id
        card_numbers_related_to_card_ids = await self.select_all(
            sa_select(models.Card.card_number, models.Card.id),
            scalars=False
        )
        card_numbers_related_to_card_ids = {item[0]: item[1] for item in card_numbers_related_to_card_ids}

        # Система. Сопоставление id записи на мигрируемом сервере с id на новом
        system_ids = await self.select_all(
            sa_select(models.System.master_db_id, models.System.id).where(models.System.master_db_id != None),
            scalars=False
        )
        system_ids = {item[0]: item[1] for item in system_ids}

        # Баланс. Сопоставление id организации на мигрируемом сервере с id баланса на новом
        balance_ids = await self.select_all(
            sa_select(models.Company.master_db_id, models.Balance.id)
            .where(models.Company.master_db_id != None)
            .where(models.Company.id == models.Balance.company_id),
            scalars=False
        )
        balance_ids = {item[0]: item[1] for item in balance_ids}

        # Лицевой счет. Сопоставление id организации на мигрируемом сервере с её ЛС на новом
        personal_accounts = await self.select_all(
            sa_select(models.Company.master_db_id, models.Company.personal_account),
            scalars=False
        )
        personal_accounts = {item[0]: item[1] for item in personal_accounts}

        # Тариф. Сопоставление id записи на мигрируемом сервере с наименованием тарифа на новом
        tariff_ids = await self.select_all(
            sa_select(models.Tariff.master_db_id, models.Tariff.id).where(models.Tariff.master_db_id != None),
            scalars=False
        )
        rate_ids_related_to_tariff_ids = {item[0]: item[1] for item in tariff_ids}

        # Функция получения id тарифа для организации, которой принадлежит карта
        def get_tariff_id(master_db_id: Dict[str, Any]) -> int | None:
            # Проверяем id организации на мигрируемом сервере
            if not master_db_id:
                return None

            for company in companies:
                # Ищем запись об организации на мигрируемом сервере
                if company['id'] == master_db_id:
                    # Получаем id тарифа на новом сервере
                    tariff_id = rate_ids_related_to_tariff_ids[company['rate_id']]
                    return tariff_id

        # Создаем записи в таблице contract
        company_system_relations = {}
        for transaction in transactions:
            if transaction['company_id'] in company_system_relations:
                company_system_relations[transaction['company_id']].add(transaction['system_id'])
            else:
                company_system_relations[transaction['company_id']] = {transaction['system_id']}

        cs_relations = []
        for company_id, rel_system_ids in company_system_relations.items():
            for system_id in rel_system_ids:
                if system_id:
                    cs_relations.append({"company_id": company_id, "system_id": system_id})

        dataset = [
            dict(
                tariff_id=get_tariff_id(relation['company_id']),
                balance_id=balance_ids[relation['company_id']],
                number=personal_accounts[relation['company_id']] + str(random.randint(1, 9999999)),
                system_id=system_ids[relation['system_id']],
            ) for relation in cs_relations
        ]
        await self.bulk_insert_or_update(models.Contract, dataset)

        # Договор. Сопоставление id организации на мигрируемом сервере с id договора на новом
        contract_ids = await self.select_all(
            sa_select(models.Company.master_db_id, models.Contract.id)
            .where(models.Company.master_db_id != None)
            .where(models.Balance.company_id == models.Company.id)
            .where(models.Contract.balance_id == models.Balance.id),
            scalars=False
        )
        contract_ids = {item[0]: item[1] for item in contract_ids}

        # Создаем записи в таблице card_contract
        dataset = [
            dict(
                card_id=card_numbers_related_to_card_ids[str(card['card_num'])],
                contract_id=contract_ids[card['company_id']]
            ) for card in cards if card['company_id']
        ]
        await self.bulk_insert_or_update(models.CardContract, dataset)

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

        # Система. Сопоставление id записи на боевом сервере с id на новом сервере.
        system_ids = await self.select_all(
            sa_select(models.System.master_db_id, models.System.id).where(models.System.master_db_id != None),
            scalars=False
        )
        system_ids = {item[0]: item[1] for item in system_ids}

        # Наименования товаров в привязке к id
        inner_goods_ids = await self.select_all(
            sa_select(models.InnerGoods.name, models.InnerGoods.id),
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

        await self.bulk_insert_or_update(models.OuterGoods, dataset)

    async def import_transactions(self, transactions: list[Dict[str, Any]]) -> None:
        # Номера карт в привязке к id
        card_numbers_related_to_card_ids = await self.select_all(
            sa_select(models.Card.card_number, models.Card.id),
            scalars=False
        )
        card_numbers_related_to_card_ids = {item[0]: item[1] for item in card_numbers_related_to_card_ids}

        # Договор. Сопоставление id организации на мигрируемом сервере с id договора на новом
        contract_ids = await self.select_all(
            sa_select(models.Company.master_db_id, models.Contract.id)
            .where(models.Company.master_db_id != None)
            .where(models.Balance.company_id == models.Company.id)
            .where(models.Contract.balance_id == models.Balance.id),
            scalars=False
        )
        contract_ids = {item[0]: item[1] for item in contract_ids}
        print('contract_ids:', contract_ids)

        # Коды товаров/услуг в привязке к id
        goods = await self.select_all(
            sa_select(models.InnerGoods.name, models.OuterGoods.id)
            .where(models.OuterGoods.inner_goods_id == models.InnerGoods.id),
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
                card_id=card_numbers_related_to_card_ids[str(transaction['card_num'])] if transaction['card_num']
                else None,
                contract_id=contract_ids[transaction['company_id']] if transaction['company_id'] else None,
                azs_code=transaction['azs'],
                azs_address=transaction['address'],
                outer_goods_id=goods_ids[transaction['gds']] if transaction['gds'] in goods_ids else None,
                fuel_volume=transaction['volume'],
                price=transaction['price'],
                transaction_sum=transaction['sum'],
                fee_sum=transaction['sum_service'],
                total_sum=transaction['total'],
                company_balance=0,  # После импорта будет выполнен пересчет балансов, поле примет новые значения
                comments=transaction['comment'],
            ) for transaction in transactions
        ]

        await self.bulk_insert_or_update(models.Transaction, dataset)
