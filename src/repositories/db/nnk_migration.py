import traceback
from datetime import datetime
from typing import Dict, Any

from sqlalchemy import select as sa_select, delete as sa_delete, null

from src.auth.manager import create_user
from src.database.model.card import CardOrm
from src.database.model.card_type import CardTypeOrm
from src.database.model.models import (Role as RoleOrm, System as SystemOrm, Company as CompanyOrm, Balance as BalanceOrm,
                                       Tariff as TariffOrm, OuterGoods as OuterGoodsOrm, Car as CarOrm,
                                       InnerGoods as InnerGoodsOrm, CardSystem as CardSystemOrm,
                                       BalanceSystemTariff as BalanceSystemTariffOrm, Transaction as TransactionOrm)
from src.repositories.base import BaseRepository
from src.schemas.user import UserCreateSchema
from src.utils import enums
from src.utils.common import make_personal_account
from src.utils.enums import TransactionType
from src.utils.exceptions import DBException


class NNKMigration(BaseRepository):
    system_ids = None
    balance_ids = None
    card_ids = None
    tariff_ids = None
    company_ids = None
    goods_ids = None

    async def _set_system_ids(self) -> None:
        system_ids = await self.select_all(
            sa_select(SystemOrm.master_db_id, SystemOrm.id).where(SystemOrm.master_db_id.is_not(null())),
            scalars=False
        )
        self.system_ids = {item[0]: item[1] for item in system_ids}

    async def _set_balance_ids(self) -> None:
        balance_ids = await self.select_all(
            sa_select(CompanyOrm.master_db_id, BalanceOrm.id)
            .where(CompanyOrm.master_db_id.is_not(null()))
            .where(CompanyOrm.id == BalanceOrm.company_id),
            scalars=False
        )
        self.balance_ids = {item[0]: item[1] for item in balance_ids}

    async def _set_card_ids(self) -> None:
        card_numbers_related_to_card_ids = await self.select_all(
            sa_select(CardOrm.card_number, CardOrm.id),
            scalars=False
        )
        self.card_ids = {item[0]: item[1] for item in card_numbers_related_to_card_ids}

    async def _set_company_ids(self) -> None:
        company_ids = await self.select_all(
            sa_select(CompanyOrm.master_db_id, CompanyOrm.id).where(CompanyOrm.master_db_id.is_not(null())),
            scalars=False
        )
        self.company_ids = {item[0]: item[1] for item in company_ids}

    async def _set_tariff_ids(self) -> None:
        tariff_ids = await self.select_all(
            sa_select(TariffOrm.master_db_id, TariffOrm.id).where(TariffOrm.master_db_id.is_not(null())),
            scalars=False
        )
        self.tariff_ids = {item[0]: item[1] for item in tariff_ids}

    async def _set_goods_ids(self) -> None:
        goods = await self.select_all(
            sa_select(InnerGoodsOrm.name, OuterGoodsOrm.id)
            .where(OuterGoodsOrm.inner_goods_id == InnerGoodsOrm.id),
            scalars=False
        )
        self.goods_ids = {item[0]: item[1] for item in goods}

    async def import_systems(self, systems: list[Dict[str, Any]]) -> None:
        dataset = [
            dict(
                master_db_id=system['id'],
                full_name=system['full_name'],
                short_name=system['short_name'],
                transaction_days=system['transaction_days'] if system['transaction_days'] else 30,
            ) for system in systems
        ]
        await self.bulk_insert_or_update(SystemOrm, dataset, 'full_name')
        await self._set_system_ids()

    async def import_tariffs(self, tariffs: list[Dict[str, Any]]) -> None:
        dataset = [
            dict(
                master_db_id=tariff['id'],
                name=tariff['title'],
                fee_percent=tariff['service_online'] if tariff['title'] != 'РН-ННК1.5' else 1.5,
            ) for tariff in tariffs
        ]
        await self.bulk_insert_or_update(TariffOrm, dataset, 'name')
        await self._set_tariff_ids()

    async def import_companies(self, companies: list[Dict[str, Any]]) -> None:
        # Создаем записи в таблице company
        dataset = [
            dict(
                master_db_id=company['id'],
                name=company['name'],
                date_add=company['date_add'],
                personal_account=make_personal_account(),
                inn=company['inn'],
                min_balance=0,
            ) for company in companies
        ]
        await self.bulk_insert_or_update(CompanyOrm, dataset)
        await self._set_company_ids()

    async def import_balances(self, companies: list[Dict[str, Any]]) -> None:
        # Для каждой организации создаем единственный баланс (для перекупной схемы)
        dataset = [
            dict(
                company_id=self.company_ids[company['id']],
                scheme=enums.ContractScheme.OVERBOUGHT.name,
                balance=company['amount'],
                min_balance_period_end_date=None if company['min_balance_date_to'] == '0000-00-00 00:00:00' else
                company['min_balance_date_to'],
                min_balance_on_period=company['min_balance_period'],
            ) for company in companies
        ]
        await self.bulk_insert_or_update(BalanceOrm, dataset)
        await self._set_balance_ids()

    async def import_cars(self, cars: list[Dict[str, Any]]) -> None:
        dataset = [
            dict(
                master_db_id=car['id'],
                reg_number=car['car_number'],
                company_id=self.company_ids[car['company_id']],
            ) for car in cars
        ]
        await self.bulk_insert_or_update(CarOrm, dataset)

    async def import_cards(self, cards: list[Dict[str, Any]]) -> None:
        # Тип карты по умолчанию для вновь импортируемых карт
        plastic_card_type = await self.insert_or_update(CardTypeOrm, 'name', name="Пластиковая карта")

        # Номера карт в привязке к типам (для существующих карт)
        card_numbers_related_to_card_type_ids = await self.select_all(
            sa_select(CardOrm.card_number, CardOrm.card_type_id),
            scalars=False
        )
        card_numbers_related_to_card_type_ids = {
            item[0]: item[1] for item in card_numbers_related_to_card_type_ids
        }

        # Автомобиль. Сопоставление id записи на боевом сервере с id на новом сервере.
        car_ids = await self.select_all(
            sa_select(CarOrm.master_db_id, CarOrm.id).where(CarOrm.master_db_id.is_not(null())),
            scalars=False
        )
        car_ids = {item[0]: item[1] for item in car_ids}

        dataset = [
            dict(
                card_type_id=card_numbers_related_to_card_type_ids.get(card['card_num'], plastic_card_type.id),
                company_id=self.company_ids[card['company_id']] if card['company_id'] else None,
                card_number=card['card_num'],
                belongs_to_car_id=car_ids[card['car_id']] if card['car_id'] else None,
                is_active=card['state'],
                manual_lock=card['manual_lock'],
            ) for card in cards
        ]
        await self.bulk_insert_or_update(CardOrm, dataset, 'card_number')
        await self._set_card_ids()

    async def bind_cards_with_systems(self, cards: list[Dict[str, Any]]) -> None:
        """
        Создаем записи в таблице card_system - связываем карты с соответствующими системой
        """
        dataset = [
            dict(
                card_id=self.card_ids[str(card['card_num'])],
                system_id=self.system_ids[card['system_id']]
            ) for card in cards if card['system_id']
        ]
        await self.bulk_insert_or_update(CardSystemOrm, dataset)

        # Карты Роснефти открепляем от организаций
        stmt = sa_select(SystemOrm).where(SystemOrm.short_name == 'РН')
        rosneft_system = await self.select_first(stmt)

        stmt = (
            sa_select(CardOrm)
            .select_from(CardOrm, CardSystemOrm)
            .where(CardSystemOrm.system_id == rosneft_system.id)
            .where(CardOrm.id == CardSystemOrm.card_id)
        )
        cards = await self.select_all(stmt)
        dataset = [
            {
                "id": card.id,
                "company_id": None,
                "belongs_to_car_id": None,
                "belongs_to_driver_id": None,
                "is_active": False,
            } for card in cards
        ]
        await self.bulk_update(CardOrm, dataset)

        # Карты Роснефти открепляем от системы
        card_ids = [card.id for card in cards]
        stmt = (
            sa_delete(CardSystemOrm)
            .where(CardSystemOrm.card_id.in_(card_ids))
            .where(CardSystemOrm.system_id == rosneft_system.id)
        )
        try:
            await self.session.execute(stmt)
            await self.session.commit()

        except Exception:
            self.logger.error(traceback.format_exc())
            raise DBException()

    async def import_tariffs_history(self, companies: list[Dict[str, Any]]) -> None:
        # Создаем записи в таблице balance_system_tariff
        # Для всех организаций делаем связку: системы, в которых работает организация,
        # привязываем к соответствующему балансу (сейчас он один у каждой организации),
        # указываем какой тариф при этом следует использовать.
        # Привязку выполняем только для ННК, так как на данный момент работа ведется только в этой системе.

        # ННК
        nnk_system = await self.select_first(sa_select(SystemOrm).where(
            SystemOrm.full_name == "АО «ННК-Хабаровскнефтепродукт»")
        )
        dataset = [
            dict(
                balance_id=self.balance_ids[company['id']],
                system_id=nnk_system.id,
                tariff_id=self.tariff_ids[company['tariff_id']],
            ) for company in companies if company['tariff_id']
        ]
        await self.bulk_insert_or_update(BalanceSystemTariffOrm, dataset)

    async def import_inner_goods(self, goods: list[Dict[str, Any]]) -> None:
        dataset = [{'name': good['inner_goods']} for good in goods if good['inner_goods']]
        await self.bulk_insert_or_update(InnerGoodsOrm, dataset)

    async def import_outer_goods(self, goods: list[Dict[str, Any]]) -> None:
        # Пример входной строки goods:
        # {
        #     "system_id": System.master_db_id,
        #     "outer_goods": OuterGoods.name,
        #     "inner_goods": InnerGoods.name
        # }

        # Наименования товаров в привязке к id
        inner_goods_ids = await self.select_all(
            sa_select(InnerGoodsOrm.name, InnerGoodsOrm.id),
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

        await self.bulk_insert_or_update(OuterGoodsOrm, dataset)
        await self._set_goods_ids()

    async def import_transactions(self, transactions: list[Dict[str, Any]]) -> None:
        dataset = [
            dict(
                master_db_id=transaction['id'],
                external_id=transaction['id'],
                date_time=datetime.fromisoformat(transaction['date']),
                # date_time_load=datetime.fromisoformat(transaction['date_load']),
                date_time_load=datetime.fromtimestamp(transaction['date_load_2']),
                transaction_type=self.get_transaction_type(transaction),
                card_id=self.card_ids[str(transaction['card_num'])] if transaction['card_num']
                else None,
                balance_id=self.balance_ids[transaction['company_id']] if transaction['company_id'] else None,
                system_id=self.system_ids[transaction['system_id']] if transaction['system_id'] else None,
                azs_code=transaction['azs'],
                azs_address=transaction['address'],
                outer_goods_id=self.goods_ids[transaction['gds']] if transaction['gds'] in self.goods_ids else None,
                fuel_volume=transaction['volume'],
                price=transaction['price'],
                transaction_sum=transaction['sum'],
                tariff_id=None,
                fee_sum=transaction['sum_service'],
                total_sum=transaction['total'],
                company_balance=transaction['balance'],
                comments=transaction['comment'],
            ) for transaction in transactions
        ]

        await self.bulk_insert_or_update(TransactionOrm, dataset)

    @staticmethod
    def get_transaction_type(transaction: Dict[str, Any]) -> TransactionType:
        if transaction['sum'] < 0:
            # Дебетование: покупка или ручное уменьшение
            return TransactionType.PURCHASE if transaction['sum_service'] else TransactionType.DECREASE
        else:
            # Кредитование: возврат или пополнение
            return TransactionType.REFUND if transaction['sum_service'] else TransactionType.REFILL

    async def import_users(self, users: list[Dict[str, Any]]) -> None:
        superadmins = [
            ('admin', 'Администратор', 'Cargonomica'),
            ('a.voskresenskiy', 'А.', 'Воскресенский'),
            ('a.ivanov', 'А.', 'Иванов'),
            ('v.romm', 'В.', 'Ромм'),
            ('a.ermakova', 'А.', 'Ермакова'),
        ]

        # Получаем роль администратора организации
        stmt = sa_select(RoleOrm).where(RoleOrm.name == enums.Role.COMPANY_ADMIN.name)
        company_admin_role = await self.select_first(stmt)

        # Создаем пользователей
        self.logger.info("Создаю пользователей")
        for user in users:
            if not list(filter(lambda sa: user['email'] == sa[0] + '@cargonomica.com', superadmins)):
                phone = ''.join([num for num in str(user['phone']) if num.isdecimal()])
                fio = user['fio'].split(maxsplit=1)
                user_schema = UserCreateSchema(
                    username=user['email'],
                    password=user['password'],
                    first_name=fio[1] if len(fio) > 1 else "",
                    last_name=fio[0],
                    email=user['email'],
                    phone=phone[:12],
                    is_active=True,
                    role_id=company_admin_role.id,
                    company_id=self.company_ids.get(user['company_id'], None) if user['company_id'] else None
                )
                await create_user(user_schema)

        # Получаем роль суперадмина
        stmt = sa_select(RoleOrm).where(RoleOrm.name == enums.Role.CARGO_SUPER_ADMIN.name)
        superadmin_role = await self.select_first(stmt)

        # Создаем суперадминов
        for superadmin in superadmins:
            user_schema = UserCreateSchema(
                username=superadmin[0],
                password='Five432!',
                first_name=superadmin[2],
                last_name=superadmin[1],
                email=superadmin[0] + '@cargonomica.com',
                phone='111',
                is_active=True,
                role_id=superadmin_role.id
            )
            await create_user(user_schema)
