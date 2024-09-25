import math
from datetime import datetime
from typing import Dict, Any, List

from sqlalchemy import select as sa_select, delete as sa_delete, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, selectinload, aliased, load_only

from src.celery_app.exceptions import CeleryError
from src.celery_app.gpn.api import GPNApi, GpnGoodsCategory
from src.celery_app.irrelevant_balances import IrrelevantBalances
from src.celery_app.transaction_helper import TransactionHelper
from src.config import TZ
from src.database.models import CompanyOrm, CardLimitOrm, AzsOrm, RegionOrm, GroupLimitOrm, CardGroupOrm, CheckReportOrm
from src.database.models.azs import AzsOwnType
from src.database.models.balance_system import BalanceSystemOrm
from src.database.models.card import CardOrm, BlockingCardReason
from src.database.models.card_type import CardTypeOrm
from src.database.models.check_report import CheckReport
from src.database.models.goods import OuterGoodsOrm
from src.database.models.goods_category import GoodsCategory
from src.database.models.system import CardSystemOrm
from src.database.models.transaction import TransactionOrm
from src.repositories.base import BaseRepository
from src.repositories.card import CardRepository
from src.repositories.company import CompanyRepository
from src.repositories.system import SystemRepository
from src.repositories.tariff import TariffRepository
from src.repositories.transaction import TransactionRepository
from src.repositories.user import UserRepository
from src.utils.common import calc_available_balance, banking_round
from src.utils.enums import ContractScheme, System, Role
from src.utils.loggers import get_logger

personal_account_str = str
delta_sum_float = float


class GPNController(BaseRepository):

    def __init__(self, session: AsyncSession):
        super().__init__(session, None)
        self.logger = get_logger(name="GPNController", filename="celery.log")
        self.api = GPNApi()
        self.system = None
        self._irrelevant_balances = None
        self.card_groups = None
        self.card_types = {}

        self._bst_list: List[BalanceSystemOrm] = []

        self.helper: TransactionHelper | None = None

    async def init(self) -> None:
        await self.init_system()
        self._irrelevant_balances = IrrelevantBalances(system_id=self.system.id)
        self.helper = TransactionHelper(session=self.session, logger=self.logger, system_id=self.system.id)

    async def init_system(self) -> None:
        system_repository = SystemRepository(self.session)
        self.system = await system_repository.get_system_by_short_name(
            short_name=System.GPN.value,
            scheme=ContractScheme.OVERBOUGHT
        )

    async def sync(self) -> IrrelevantBalances:
        # Прогружаем наш баланс
        await self.load_balance()

        # Синхронизируем карты по номеру
        # await self.sync_cards()

        # Прогружаем транзакции
        await self.load_transactions()

        # Возвращаем объект со списком транзакций, начиная с которых требуется пересчитать балансы
        return self._irrelevant_balances

    async def load_balance(self) -> None:
        contract_data = self.api.contract_info()
        balance = float(contract_data['balanceData']['available_amount'])
        self.logger.info('Наш баланс в системе {}: {} руб.'.format(self.system.full_name, balance))

        # Обновляем запись в локальной БД
        await self.update_object(self.system, update_data={
            "balance": balance,
            "balance_sync_dt": datetime.now(tz=TZ)
        })

    async def service_sync(self) -> None:
        """
        1. Синхронизируем группы карт
        2. Синхронизируем карты
        3. Синхронизируем лимиты на группы.
        """

        # ---- 1 ----

        # Получаем список карт от системы ГПН
        remote_cards = self.api.get_gpn_cards()
        self.logger.info(f"Количество карт в API ГПН: {len(remote_cards)}")

        # Синхронизируем группы карт
        self.logger.info("Запускаю синхронизацию карточных групп")
        await self.sync_card_groups(remote_cards)
        self.logger.info("Синхронизация карточных групп завершена")

        # ---- 2 ----

        # Синхронизируем карты
        self.logger.info("Запускаю синхронизацию карт")
        await self.sync_cards(remote_cards)
        self.logger.info("Синхронизация карт завершена")

        # ---- 3 ----
        # Устанавливаем лимиты на группы
        self.logger.info("Запускаю синхронизацию лимитов на группы карт")
        await self.sync_group_limits()
        self.logger.info("Синхронизация лимитов завершена")

    async def get_card_types(self, gpn_cards: List[Dict[str, Any]]) -> None:
        """
        Получаем из локальной БД список типов карт, соответствующих типам карт в ГПН.
        Если в локальной БД не найдено, то создаем новые типы.
        """
        gpn_card_type_names = [card["carrier_name"] for card in gpn_cards]
        stmt = sa_select(CardTypeOrm).where(CardTypeOrm.name.in_(gpn_card_type_names))
        local_card_types_dataset = await self.select_all(stmt)

        if len(gpn_card_type_names) != len(local_card_types_dataset):
            local_card_type_names = [ct.name for ct in local_card_types_dataset]
            new_card_types = []
            for gpn_card_type_name in gpn_card_type_names:
                if gpn_card_type_name not in local_card_type_names:
                    new_card_types.append({"name": gpn_card_type_name})

            await self.bulk_insert_or_update(CardTypeOrm, new_card_types, index_field="name")

            stmt = sa_select(CardTypeOrm).where(CardTypeOrm.name.in_(gpn_card_type_names))
            local_card_types_dataset = await self.select_all(stmt)

        self.card_types = {data.name: data for data in local_card_types_dataset}

    async def sync_card_groups(self, remote_cards: List[Dict[str, Any]]) -> None:
        self.logger.info("Запускаю синхронизацию групп карт")
        # Из локальной БД получаем список организаций, которым присвоены карты ГПН.
        stmt = (
            sa_select(CompanyOrm)
            .options(
                selectinload(CompanyOrm.card_groups)
                .joinedload(CardGroupOrm.system)
            )
            .select_from(CompanyOrm, CardOrm, CardSystemOrm)
            .where(CompanyOrm.id == CardOrm.company_id)
            .where(CardOrm.id == CardSystemOrm.card_id)
            .where(CardSystemOrm.system_id == self.system.id)
        )
        companies = await self.select_all(stmt)

        # Из API получаем список групп карт
        gpn_groups = self.api.get_card_groups()

        # Сравниваем непосредственно группы карт.
        # Если в БД отсутствует запись о группе, создаем её.
        # Сверенные группы удаляем из списков для уменьшения стоимости алгоритма.
        i = 0
        while i < len(companies):
            company = companies[i]
            found = False
            for gpn_group in gpn_groups:
                if gpn_group['name'] == company.personal_account:
                    # В списке из БД найдена организация с ЛС, соответствующим наименованием группы в ГПН.
                    found = True

                    # Проверяем существование записи о группе в локальной БД
                    if not company.has_card_group(System.GPN.value):
                        card_group = CardGroupOrm(
                            system_id=self.system.id,
                            external_id=gpn_group["id"],
                            name=company.personal_account,
                            company_id=company.id
                        )
                        await self.save_object(card_group)
                        self.logger.info(f"В БД создана группа карт системы ГПН для организации {company.name}")

                    # Сокращаем списки
                    companies.remove(company)
                    gpn_groups.remove(gpn_group)
                    break

            if not found:
                # Совпадающая группа НЕ найдена, переходим к следующей.
                i += 1

        # Удаляем в API избыточные группы.
        for group in gpn_groups:
            # В ГПН открепляем карты от группы
            self.api.unbind_cards_from_group(
                card_numbers=[card['number'] for card in remote_cards if card['group_id'] == group['id']],
                card_external_ids=[card['id'] for card in remote_cards if card['group_id'] == group['id']],
                group_id=group['id']
            )

            # Удаляем группу ГПН
            self.api.delete_gpn_group(group_id=group['id'], group_name=group['name'])

        # Создаем в API и в БД недостающие группы.
        for company in companies:
            group_id = self.api.create_card_group(company.personal_account)
            card_group = CardGroupOrm(
                system_id=self.system.id,
                external_id=group_id,
                name=company.personal_account,
                company_id=company.id
            )
            await self.save_object(card_group)
            self.logger.info(f"В БД создана группа карт системы ГПН для организации {company.name}")

    async def sync_cards(self, remote_cards: List[Dict[str, Any]]) -> None:
        # Получаем типы карт
        await self.get_card_types(remote_cards)

        # Получаем список карт из БД
        local_cards = await self.helper.get_local_cards()
        self.logger.info(f"Количество карт в локальной БД (до синхронизации): {len(local_cards)}")

        # Создаем в локальной БД новые карты и привязываем их к ГПН. Статус карты из ГПН транслируем на локальную БД.
        # Привязываем в локальной БД карты, открепленные от ГПН - статус не устанавливаем.
        local_card_numbers = [local_card.card_number for local_card in local_cards]
        for remote_card in remote_cards:
            if remote_card['number'] not in local_card_numbers:
                is_active = True if "locked" not in remote_card["status"].lower() else False
                await self.bind_or_create_card(
                    card_number=remote_card['number'],
                    card_type_name=remote_card["carrier_name"],
                    is_active=is_active
                )

        # Из локальной БД заново получаем список карт, привязанных к ГПН
        local_cards = await self.helper.get_local_cards()
        self.logger.info(f"Количество карт в локальной БД (после синхронизации): {len(local_cards)}")

        # Из API получаем группы карт
        gpn_card_groups = self.api.get_card_groups()
        gpn_group_id_by_name = {gpn_card_group['name']: gpn_card_group['id'] for gpn_card_group in gpn_card_groups}
        gpn_group_name_by_id = {gpn_card_group['id']: gpn_card_group['name'] for gpn_card_group in gpn_card_groups}

        # Сравниваем ЛС организаций, которым принадлежат карты с группами ГПН.
        # Записи в локальной БД имеют первичное значение.

        # Открепляем от групп карты, которые в них не должны состоять
        gpn_cards_dict = {card['number']: card for card in remote_cards}
        for local_card in local_cards:
            gpn_card = gpn_cards_dict[local_card.card_number]
            if gpn_card['group_id']:
                if not local_card.company_id \
                        or local_card.company.personal_account != gpn_group_name_by_id[gpn_card['group_id']]:
                    self.api.unbind_cards_from_group(
                        card_numbers=[local_card.card_number],
                        card_external_ids=[local_card.external_id],
                        group_id=gpn_card['group_id']
                    )

        # Прикрепляем к группам карты, которые должны в них состоять, но не состоят
        binding_data = {}
        for local_card in local_cards:
            gpn_card = gpn_cards_dict[local_card.card_number]
            if local_card.company_id:
                true_group_id = gpn_group_id_by_name[local_card.company.personal_account]
                if gpn_card['group_id'] != true_group_id:
                    if true_group_id in binding_data:
                        binding_data[true_group_id].append(gpn_card['id'])
                    else:
                        binding_data[true_group_id] = [gpn_card['id']]

        for group_id, card_external_ids in binding_data.items():
            self.api.bind_cards_to_group(
                card_numbers=[local_card.card_number for local_card in local_cards
                              if local_card.external_id in card_external_ids],
                card_external_ids=card_external_ids,
                group_id=group_id
            )

        # Записываем в БД время последней успешной синхронизации
        await self.update_object(self.system, update_data={"cards_sync_dt": datetime.now(tz=TZ)})
        self.logger.info('Синхронизация карт выполнена')

    async def sync_group_limits(self):
        """Функция выполняет проверку соответствия групповых лимитов, записанных в локальную БД,
        с групповыми лимитами ГПН."""

        personal_accounts_for_test = []

        """Получаем данные из локальной БД"""
        # Из локальной БД получаем список организаций, которым присвоены карты ГПН.
        stmt = (
            sa_select(CompanyOrm)
            .options(
                selectinload(CompanyOrm.card_groups)
                .joinedload(CardGroupOrm.system)
            )
            .options(
                selectinload(CompanyOrm.group_limits)
                .joinedload(GroupLimitOrm.system)
            )
            .options(
                selectinload(CompanyOrm.balances)
            )

            .select_from(CompanyOrm, CardOrm, CardSystemOrm)
            .where(CompanyOrm.id == CardOrm.company_id)
            .where(CardOrm.id == CardSystemOrm.card_id)
            .where(CardSystemOrm.system_id == self.system.id)
            .order_by(CompanyOrm.personal_account)
        )
        if personal_accounts_for_test:
            stmt = stmt.where(CompanyOrm.personal_account.in_(personal_accounts_for_test))

        companies = await self.select_all(stmt)

        """Формируем структуру с дополнительной информацией к списку организаций.
        В ней будут храниться данные о категориях, по которым у организации есть карточные лимиты, 
        и "правильный" размер доступного лимита ДС"""
        additional_companies_data = {}

        # Присоединяем информацию о "правильных" лимитах
        for company in companies:
            available_balance = calc_available_balance(
                current_balance=company.overbought_balance().balance,
                min_balance=company.min_balance,
                overdraft_on=company.overdraft_on,
                overdraft_sum=company.overdraft_sum
            )
            additional_companies_data[company.personal_account] = {
                "available_balance": available_balance,
                "card_limit_categories": []
            }

        # Получаем из БД информацию у каких организаций на какие категории продуктов установлены карточные лимиты
        stmt = (
            sa_select(CompanyOrm.personal_account, CardLimitOrm.inner_goods_category)
            .select_from(CompanyOrm, CardOrm, CardLimitOrm)
            .where(CardOrm.id == CardLimitOrm.card_id)
            .where(CardLimitOrm.system_id == self.system.id)
            .where(CompanyOrm.id == CardOrm.company_id)
            .order_by(CompanyOrm.personal_account)
            .distinct()
        )
        if personal_accounts_for_test:
            stmt = stmt.where(CompanyOrm.personal_account.in_(personal_accounts_for_test))

        company_card_limit_dataset = await self.select_all(stmt, scalars=False)

        # Присоединяем информацию о категориях продуктов с установленными карточными лимитами
        for card_limit_data in company_card_limit_dataset:
            personal_account = card_limit_data[0]
            card_limit_category = card_limit_data[1]
            additional_companies_data[personal_account]["card_limit_categories"].append(card_limit_category)

        # Из API получаем список карточных групп
        gpn_groups = self.api.get_card_groups()

        """Вспомогательные функции"""

        def count_local_limits_by_category(_gpn_category: GpnGoodsCategory,
                                           _local_group_limits: List[GroupLimitOrm]) -> int:
            count = 0
            for _local_limit in _local_group_limits:
                if _local_limit.system_id == self.system.id \
                        and _local_limit.inner_goods_category == _gpn_category.value["local_category"]:
                    count += 1

            return count

        def count_remote_limits_by_category(_gpn_category: GpnGoodsCategory,
                                            _remote_group_limits: List[Dict[str, Any]]) -> int:
            i = 0
            for _remote_limit in _remote_group_limits:
                if _remote_limit["productType"] == _gpn_category.value["id"]:
                    i += 1

            return i

        def get_local_limit_by_category(_gpn_category: GpnGoodsCategory,
                                        _local_group_limits: List[GroupLimitOrm]) -> GroupLimitOrm | None:
            for _local_limit in _local_group_limits:
                if _local_limit.system_id == self.system.id \
                        and _local_limit.inner_goods_category == _gpn_category.value["local_category"]:
                    return _local_limit

        def get_remote_limit_by_category(_gpn_category: GpnGoodsCategory,
                                         _remote_group_limits: List[Dict[str, Any]]) -> Dict[str, Any] | None:
            for _remote_limit in _remote_group_limits:
                if _remote_limit["productType"] == _gpn_category.value["id"]:
                    return _remote_limit

        def get_right_limit_sum(_company: CompanyOrm, _inner_goods_category: GoodsCategory,
                                _card_limit_categories: List[GoodsCategory]) -> int:

            _available_balance = additional_companies_data[_company.personal_account]["available_balance"]
            if _inner_goods_category == GoodsCategory.FUEL or _inner_goods_category in _card_limit_categories:
                # Если категория - "Топливо", или задан карточный лимит на эту категорию,
                # то правильный групповой лимит должен быть равен доступному остатку ДС организации.
                _right_limit_sum = max(int(math.floor(_available_balance)), 1)

            else:
                # Если категория не "Топливо" и не задан карточный лимит на эту категорию,
                # то правильный групповой лимит должен быть равен 1 руб.
                _right_limit_sum = 1

            return _right_limit_sum

        async def check_group_limit_sum(_company: CompanyOrm, _local_group_limit: GroupLimitOrm,
                                        _remote_group_limit: Dict[str, Any]) -> None:
            """Функция проверяет правильно ли задан групповой лимит локально и в ГПН. Предполагается, что
            необходимые проверки уже выполнены и существует только 1 лимит локально и ему соответствует
            только 1 лимит в ГПН."""

            if _remote_group_limit["sum"]["value"] > 1400000:
                # Если в ГПН установленный лимит выше 1,4 млн, то в ГПН удаляем существующий лимит и создаем новый
                self.logger.info(
                    f"Текущее значение лимит ГПН {_remote_group_limit['sum']['value']} превышает 1,4 млн. "
                    f"Пересоздаю лимит. Организация {_company.name} {_company.personal_account}, категория: "
                    f"{_local_group_limit.inner_goods_category.name}"
                )
                try:
                    # Удаляем лимит ГПН
                    self.api.delete_group_limit(
                        limit_id=_remote_group_limit["id"],
                        group_id=group.external_id
                    )

                    # Создаем новый групповой лимит ГПН
                    _limit_external_id = self._set_group_limit(
                        limit_id=None,
                        group_id=group.external_id,
                        gpn_goods_category=GpnGoodsCategory.get_equal_by_local(_local_group_limit.inner_goods_category),
                        limit_sum=right_limit_sum,
                        company_name=_company.name,
                        personal_account=_company.personal_account,
                        previous_remote_limit_sum=None,
                        previous_remote_available_sum=None
                    )

                    # Обновляем групповой лимит в БД
                    _local_group_limit.external_id = _limit_external_id
                    _local_group_limit.limit_sum = right_limit_sum
                    await self.save_object(_local_group_limit)

                except Exception:
                    self.logger.error(
                        f"Не удалось установить новый групповой лимит ГПН {right_limit_sum} р. на категорию "
                        f"{_local_group_limit.inner_goods_category.name} для оргнизации {_company.name} "
                        f"{_company.personal_account}"
                    )

                else:
                    self.logger.info(
                        f"Успешно пересоздан групповой лимит ГПН {right_limit_sum} р. на категорию "
                        f"{_local_group_limit.inner_goods_category.name} для оргнизации {_company.name} "
                        f"{_company.personal_account}"
                    )

            else:
                # Если установленный в ГПН лимит не превышает 1,4 млн, то проверяем соответствие лимитов
                # локально и в ГПН
                _current_local_available_limit_sum = int(math.floor(_local_group_limit.limit_sum))
                _current_remote_available_limit_sum = int(math.floor(
                    _remote_group_limit["sum"]["value"] - _remote_group_limit["sum"]["used"]
                ))

                if _current_remote_available_limit_sum != right_limit_sum:
                    self.logger.error(
                        f"В ГПН установлен некорректный групповой лимит {_current_remote_available_limit_sum} р. "
                        f"по категории {_local_group_limit.inner_goods_category.name} для огранизации {_company.name} "
                        f"{_company.personal_account}. Устанавливаю новое значение лимита: {right_limit_sum} р."
                    )
                    try:
                        _gpn_new_limit_sum = int(math.ceil(_remote_group_limit["sum"]["used"])) + right_limit_sum
                        gpn_goods_category = GpnGoodsCategory.get_equal_by_local(
                            _local_group_limit.inner_goods_category
                        )
                        self._set_group_limit(
                            limit_id=_remote_group_limit["id"],
                            group_id=group.external_id,
                            gpn_goods_category=gpn_goods_category,
                            limit_sum=_gpn_new_limit_sum,
                            company_name=_company.name,
                            personal_account=_company.personal_account,
                            previous_remote_limit_sum=_remote_group_limit["sum"]["value"],
                            previous_remote_available_sum=_current_remote_available_limit_sum
                        )

                    except Exception:
                        self.logger.error(
                            f"Ошибка установки группового лимита ГПН по категории "
                            f"{_local_group_limit.inner_goods_category.name} для огранизации {_company.name}"
                        )

                    if _current_local_available_limit_sum != right_limit_sum:
                        self.logger.error(
                            f"В БД установлен некорректный групповой лимит {_current_local_available_limit_sum} р. "
                            f"по категории {_local_group_limit.inner_goods_category.name} для огранизации "
                            f"{_company.name} {_company.personal_account}. Устанавливаю новое значение лимита: "
                            f"{right_limit_sum} р."
                        )
                        _local_group_limit.limit_sum = right_limit_sum
                        await self.save_object(_local_group_limit)

        """Основной программный код"""
        i = 1
        companies_amount = len(companies)
        for company in companies:
            self.logger.info(f"Организация {i} из {companies_amount}: {company.name} {company.personal_account}")
            i += 1

            group: CardGroupOrm = company.get_card_group(System.GPN.value)

            if group:
                # Проверяем наличие группы в ГПН
                found = False
                for gpn_group in gpn_groups:
                    if gpn_group["name"] == company.personal_account:
                        found = True
                        break

                if not found:
                    self.logger.error(
                        f"В ГПН отсутствует запись о карточной группе для организации {company.name} "
                        f"{company.personal_account}. Создаю группу в ГПН."
                    )

                    # Создаем карточную группу в ГПН
                    try:
                        group_id = self.api.create_card_group(company.personal_account)

                    except Exception:
                        self.logger.error("Не удалось создать карточную группа в ГПН для "
                                          f"организации {company.name} {company.personal_account}")

                    else:
                        self.logger.error(
                            f"В ГПН создана запись о карточной группе для организации {company.name} "
                            f"{company.personal_account}. Обновляю запись о группе в БД."
                        )

                        # Обновляем карточную группу в БД
                        group.external_id = group_id
                        await self.save_object(group)

            else:
                # Если группа не существует в БД, проверяем ее наличие в ГПН
                self.logger.error("В БД отсутствует запись о карточной группе ГПН для "
                                  f"организации {company.name} {company.personal_account}")
                found = False
                for gpn_group in gpn_groups:
                    if gpn_group["name"] == company.personal_account:
                        found = True
                        self.logger.error(f"В ГПН найдена запись о карточной группе ГПН для организации {company.name} "
                                          f"{company.personal_account}. Импортирую запись в БД.")
                        group = CardGroupOrm(
                            system_id=self.system.id,
                            external_id=gpn_group["id"],
                            name=company.personal_account,
                            company_id=company.id
                        )
                        await self.save_object(group)
                        break

                if not found:
                    self.logger.error(
                        f"В ГПН отсутствует запись о карточной группе для организации {company.name} "
                        f"{company.personal_account}. Создаю группу в ГПН и БД."
                    )

                    # Создаем карточную группу в ГПН
                    try:
                        group_id = self.api.create_card_group(company.personal_account)

                    except Exception:
                        self.logger.error("Не удалось создать карточную группа в ГПН для "
                                          f"организации {company.name} {company.personal_account}")

                    else:
                        # Создаем карточную группу в БД
                        group = CardGroupOrm(
                            system_id=self.system.id,
                            external_id=group_id,
                            name=company.personal_account,
                            company_id=company.id
                        )
                        await self.save_object(group)

            # Из ГПН получаем групповые лимиты
            remote_group_limits = self.api.get_card_group_limits(group.external_id)

            # Оцениваем соответствие лимитов по каждой категории продуктов.
            for gpn_category in GpnGoodsCategory:
                inner_goods_category = gpn_category.value["local_category"]
                right_limit_sum = get_right_limit_sum(
                    _company=company,
                    _inner_goods_category=inner_goods_category,
                    _card_limit_categories=additional_companies_data[company.personal_account]["card_limit_categories"]
                )

                # Выясняем сколько лимитов этой категории записано в локальную БД
                local_limits_count = count_local_limits_by_category(
                    _gpn_category=gpn_category,
                    _local_group_limits=company.group_limits
                )

                # Выясняем сколько лимитов этой категории присутствует в ГПН
                remote_limits_count = count_remote_limits_by_category(
                    _gpn_category=gpn_category,
                    _remote_group_limits=remote_group_limits
                )

                if local_limits_count == 0:
                    if remote_limits_count == 0:
                        # В ГПН не задан групповой лимит.
                        # Создаем групповой лимит в ГПН, записываем в БД
                        self.logger.error(
                            f"В БД и ГПН отсутствуют лимиты на категорию {inner_goods_category.name} для оргнизации "
                            f"{company.name} {company.personal_account}"
                        )

                        try:
                            # Создаем новый групповой лимит ГПН
                            limit_external_id = self._set_group_limit(
                                limit_id=None,
                                group_id=group.external_id,
                                gpn_goods_category=gpn_category,
                                limit_sum=right_limit_sum,
                                company_name=company.name,
                                personal_account=company.personal_account,
                                previous_remote_limit_sum=None,
                                previous_remote_available_sum=None
                            )

                        except Exception:
                            self.logger.error(
                                f"Не удалось установить новый групповой лимит ГПН {right_limit_sum} р. на категорию "
                                f"{inner_goods_category.name} для оргнизации {company.name} {company.personal_account}"
                            )

                        else:
                            self.logger.info(
                                f"Успешно создан групповой лимит ГПН {right_limit_sum} р. на категорию "
                                f"{inner_goods_category.name} для оргнизации {company.name} "
                                f"{company.personal_account}. Создаю лимит в БД."
                            )

                            # Создаем групповой лимит в БД
                            local_group_limit = GroupLimitOrm(
                                system_id=self.system.id,
                                external_id=limit_external_id,
                                company_id=company.id,
                                limit_sum=right_limit_sum,
                                inner_goods_category=inner_goods_category
                            )
                            await self.save_object(local_group_limit)

                            self.logger.info(
                                f"Успешно создан групповой лимит в БД {right_limit_sum} р. на категорию "
                                f"{inner_goods_category.name} для оргнизации {company.name} {company.personal_account}."
                            )

                    if remote_limits_count == 1:
                        # В ГПН задан 1 групповой лимит.
                        # Сверяем значение лимита в ГПН. Создаем лимит в БД.
                        self.logger.error(
                            f"В БД не найден групповой лимит на категорию {inner_goods_category.name} для оргнизации "
                            f"{company.name} {company.personal_account}. В ГПН аналогичный лимит установлен."
                        )

                        remote_group_limit = get_remote_limit_by_category(
                            _gpn_category=gpn_category,
                            _remote_group_limits=remote_group_limits
                        )

                        remote_limit_is_ok = False
                        limit_external_id = remote_group_limit["id"]

                        if remote_group_limit["sum"]["value"] > 1400000:
                            # Если в ГПН установленный лимит выше 1,4 млн,
                            # то в ГПН удаляем существующий лимит и создаем новый
                            self.logger.info(
                                f"Текущее значение лимит ГПН {remote_group_limit['sum']['value']} превышает 1,4 млн. "
                                f"Пересоздаю лимит. Организация {company.name} {company.personal_account}, категория: "
                                f"{inner_goods_category.name}"
                            )
                            try:
                                # Удаляем лимит ГПН
                                self.api.delete_group_limit(
                                    limit_id=remote_group_limit["id"],
                                    group_id=group.external_id
                                )

                                # Создаем новый групповой лимит ГПН
                                limit_external_id = self._set_group_limit(
                                    limit_id=None,
                                    group_id=group.external_id,
                                    gpn_goods_category=gpn_category,
                                    limit_sum=right_limit_sum,
                                    company_name=company.name,
                                    personal_account=company.personal_account,
                                    previous_remote_limit_sum=None,
                                    previous_remote_available_sum=None
                                )
                            except Exception:
                                self.logger.error(
                                    f"Не удалось установить новый групповой лимит ГПН {right_limit_sum} р. "
                                    f"на категорию {inner_goods_category.name} для оргнизации {company.name} "
                                    f"{company.personal_account}"
                                )

                            else:
                                self.logger.info(
                                    f"Успешно пересоздан групповой лимит ГПН {right_limit_sum} р. на категорию "
                                    f"{inner_goods_category.name} для оргнизации {company.name} "
                                    f"{company.personal_account}. Создаю аналогичный лимит в БД."
                                )
                                remote_limit_is_ok = True

                        else:
                            # Если установленный в ГПН лимит не превышает 1,4 млн,
                            # то проверяем соответствие лимита в ГПН
                            current_remote_available_limit_sum = int(math.floor(
                                remote_group_limit["sum"]["value"] - remote_group_limit["sum"]["used"]
                            ))

                            if current_remote_available_limit_sum != right_limit_sum:
                                self.logger.error(
                                    f"В ГПН установлен некорректный групповой лимит "
                                    f"{current_remote_available_limit_sum} р. по категории {inner_goods_category.name} "
                                    f"для огранизации {company.name} {company.personal_account}. "
                                    f"Устанавливаю новое значение лимита: {right_limit_sum} р."
                                )
                                try:
                                    gpn_new_limit_sum = (
                                            int(math.ceil(remote_group_limit["sum"]["used"])) + right_limit_sum
                                    )
                                    self._set_group_limit(
                                        limit_id=remote_group_limit["id"],
                                        group_id=group.external_id,
                                        gpn_goods_category=gpn_category,
                                        limit_sum=gpn_new_limit_sum,
                                        company_name=company.name,
                                        personal_account=company.personal_account,
                                        previous_remote_limit_sum=remote_group_limit["sum"]["value"],
                                        previous_remote_available_sum=current_remote_available_limit_sum
                                    )

                                except Exception:
                                    self.logger.error(
                                        f"Ошибка установки группового лимита ГПН по категории "
                                        f"{inner_goods_category.name} для огранизации {company.name}"
                                    )
                                else:
                                    self.logger.info(
                                        f"Успешно обновлен групповой лимит ГПН на категорию "
                                        f"{inner_goods_category.name} для оргнизации {company.name} "
                                        f"{company.personal_account}. Создаю аналогичный лимит в БД."
                                    )
                                    remote_limit_is_ok = True

                            else:
                                # С лимитом ГПН все в порядке
                                self.logger.info(
                                    f"Создаю в БД лимит {right_limit_sum} р. на категорию {inner_goods_category.name} "
                                    f"для оргнизации {company.name} {company.personal_account}. "
                                )
                                remote_limit_is_ok = True

                        if remote_limit_is_ok:
                            # Создаем групповой лимит в БД
                            local_group_limit = GroupLimitOrm(
                                system_id=self.system.id,
                                external_id=limit_external_id,
                                company_id=company.id,
                                limit_sum=right_limit_sum,
                                inner_goods_category=inner_goods_category
                            )
                            await self.save_object(local_group_limit)

                            self.logger.info(
                                f"Успешно создан групповой лимит в БД {right_limit_sum} р. на категорию "
                                f"{inner_goods_category.name} для оргнизации {company.name} {company.personal_account}."
                            )

                    if remote_limits_count > 1:
                        # В ГПН задано несколько групповых лимитов.
                        # Оставляем тот, у которого наименьшее значение, остальные удаляем.
                        # Сверяем значение лимита в ГПН. Создаем лимит в БД.
                        self.logger.error(
                            f"В БД не найден групповой лимит на категорию {inner_goods_category.name} для оргнизации "
                            f"{company.name} {company.personal_account}. В ГПН установлено несколько "
                            f"лимитов для этой организации по этой категории продуктов."
                        )

                elif local_limits_count == 1:
                    local_group_limit = get_local_limit_by_category(
                        _gpn_category=gpn_category,
                        _local_group_limits=company.group_limits
                    )

                    if remote_limits_count == 0:
                        # В ГПН не задан групповой лимит.
                        # Сверяем значение лимита в БД. Создаем лимит в ГПН.
                        # Лимиту в БД присваиваем идентификатор нового лимита ГПН.
                        self.logger.error(
                            f"В БД найден 1 групповой лимит на категорию {inner_goods_category.name} для оргнизации "
                            f"{company.name} {company.personal_account}. В ГПН аналогичный лимит отсутствует."
                        )
                        self.logger.info(
                            f"Создаю групповой лимит ГПН на категорию {inner_goods_category.name} "
                            f"для оргнизации {company.name} {company.personal_account}."
                        )
                        try:
                            limit_external_id = self._set_group_limit(
                                limit_id=None,
                                group_id=group.external_id,
                                gpn_goods_category=gpn_category,
                                limit_sum=right_limit_sum,
                                company_name=company.name,
                                personal_account=company.personal_account,
                                previous_remote_limit_sum=None,
                                previous_remote_available_sum=None
                            )

                        except Exception:
                            self.logger.error(
                                f"Ошибка установки группового лимита ГПН по категории "
                                f"{inner_goods_category.name} для огранизации {company.name}"
                            )
                        else:
                            self.logger.info(
                                f"Успешно создан групповой лимит ГПН на категорию {inner_goods_category.name} "
                                f"для оргнизации {company.name} {company.personal_account}. "
                                f"Обновляю соответствующий лимит в БД."
                            )
                            local_group_limit.limit_sum = right_limit_sum
                            local_group_limit.external_id = limit_external_id
                            await self.save_object(local_group_limit)

                    if remote_limits_count == 1:
                        # В ГПН задан 1 групповой лимит
                        # Так и должно быть. Сверяем значения обоих лимитов.
                        remote_group_limit = get_remote_limit_by_category(
                            _gpn_category=gpn_category,
                            _remote_group_limits=remote_group_limits
                        )

                        if local_group_limit.external_id != remote_group_limit["id"]:
                            self.logger.error("Не совпадают идентификаторы групповых лимитов (локальный и ГПН) "
                                              f"по организации {company.name}, ЛС: {company.personal_account}. "
                                              "Присваиваю локальному лимиту идентификатор лимита ГПН.")
                            local_group_limit.external_id = remote_group_limit["id"]
                            await self.save_object(local_group_limit)

                        # Сверяем суммы.
                        await check_group_limit_sum(
                            _company=company,
                            _local_group_limit=local_group_limit,
                            _remote_group_limit=remote_group_limit
                        )

                    if remote_limits_count > 1:
                        # В ГПН задано несколько групповых лимитов.
                        # Оставляем тот, у которого наименьшее значение, остальные удаляем.
                        # Лимиту в БД присваиваем идентификатор оставшегося лимита ГПН.
                        # Сверяем значения обоих лимитов.
                        self.logger.error(
                            f"В БД найден 1 групповой лимит на категорию {inner_goods_category.name} для оргнизации "
                            f"{company.name} {company.personal_account}. В ГПН установлено несколько "
                            f"лимитов для этой организации по этой категории продуктов."
                        )

    async def bind_or_create_card(self, card_number: str, card_type_name: str, is_active: bool) -> None:
        stmt = sa_select(CardOrm).where(CardOrm.card_number == card_number)
        card = await self.select_first(stmt)
        if card:
            # Карта существует, но она не привязана к ГПН. Привязываем её.
            card_system_date = {"card_id": card.id, "system_id": self.system.id}
            await self.insert(CardSystemOrm, **card_system_date)
            self.logger.info(f"Cуществующая в БД карта {card_number} привязана к системе ГПН")

        else:
            # Карта не существует в локальной БД. Создаем её.
            new_card_data = {
                "card_number": card_number,
                "card_type_id": self.card_types[card_type_name].id,
                "is_active": is_active,
            }
            new_card = await self.insert(CardOrm, **new_card_data)

            # Привязываем к системе
            card_system_date = {"card_id": new_card.id, "system_id": self.system.id}
            await self.insert(CardSystemOrm, **card_system_date)

            self.logger.info(f"В БД создана новая карта ГПН {card_number}")

    async def set_card_states(self, balance_ids_to_change_card_states: Dict[str, List[str]]):
        # В функцию переданы ID балансов, по картам которых нужно сменить состояние (заблокировать или разблокировать).
        # Меняем статус в локальной БД, потом устанавливаем новый статус в системе поставщика.

        # Получаем карты из локальной БД
        card_repository = CardRepository(self.session, None)
        local_cards_to_activate = await card_repository.get_cards_by_filters(
            balance_ids=balance_ids_to_change_card_states["to_activate"],
            system_id=self.system.id
        )
        local_cards_to_activate = [card for card in local_cards_to_activate
                                   if not card.is_active and card.reason_for_blocking != BlockingCardReason.PIN]
        local_cards_to_block = await card_repository.get_cards_by_filters(
            balance_ids=balance_ids_to_change_card_states["to_block"],
            system_id=self.system.id
        )
        local_cards_to_block = [card for card in local_cards_to_block if card.is_active]

        # Обновляем состояние карт в локальной БД
        if local_cards_to_activate or local_cards_to_block:
            dataset = [
                {
                    "id": card.id,
                    "is_active": True,
                    "reason_for_blocking": None
                } for card in local_cards_to_activate
            ]
            dataset.extend([
                {
                    "id": card.id,
                    "is_active": False,
                    "reason_for_blocking": BlockingCardReason.NNK
                } for card in local_cards_to_block
            ])
            await self.bulk_update(CardOrm, dataset)

        # Устанавливаем статусы карт в системе поставщика
        if local_cards_to_activate:
            ext_card_ids = [card.external_id for card in local_cards_to_activate]
            self.api.activate_cards(ext_card_ids)

        if local_cards_to_block:
            ext_card_ids = [card.external_id for card in local_cards_to_block]
            self.api.block_cards(ext_card_ids)

    async def load_transactions(self) -> None:
        # Получаем список транзакций от поставщика услуг
        remote_transactions = self.api.get_transactions(transaction_days=self.system.transaction_days)
        self.logger.info(f'Количество транзакций от системы ГПН: {len(remote_transactions)} шт')
        if not len(remote_transactions):
            return None

        # Получаем список транзакций из локальной БД
        transaction_repository = TransactionRepository(self.session, None)
        local_transactions = await transaction_repository.get_recent_system_transactions(
            system_id=self.system.id,
            transaction_days=self.system.transaction_days
        )
        self.logger.info(f'Количество транзакций из локальной БД: {len(local_transactions)} шт')

        # Сравниваем транзакции локальные с полученными от системы.
        # Идентичные транзакции исключаем из списков.
        self.logger.info('Приступаю к процедуре сравнения локальных транзакций с полученными от системы ГПН')
        to_delete_local = []
        for local_transaction in local_transactions:
            remote_transaction = self.get_equal_remote_transaction(local_transaction, remote_transactions)
            if remote_transaction:
                remote_transactions.remove(remote_transaction)
            else:
                # Транзакция присутствует локально, но у поставщика услуг её нет.
                # Помечаем на удаление локальную транзакцию.
                to_delete_local.append(local_transaction)
                # if local_transaction.balance_id:
                self._irrelevant_balances.add(
                    balance_id=str(local_transaction.balance_id),
                    irrelevancy_date_time=local_transaction.date_time_load
                )

                # Вычисляем дельту изменения суммы баланса - понадобится позже для правильного
                # выставления лимита на группу карт
                personal_account = local_transaction.balance.company.personal_account
                discount_fee_sum = local_transaction.discount_sum if local_transaction.discount_sum else \
                    local_transaction.fee_sum
                if personal_account in self._irrelevant_balances.decreasing_total_sum_deltas:
                    self._irrelevant_balances.decreasing_total_sum_deltas[personal_account].append(
                        local_transaction.total_sum
                    )
                    self._irrelevant_balances.decreasing_discount_fee_sum_deltas[personal_account].append(
                        discount_fee_sum
                    )
                else:
                    self._irrelevant_balances.decreasing_total_sum_deltas[personal_account] = [
                        local_transaction.total_sum
                    ]
                    self._irrelevant_balances.decreasing_discount_fee_sum_deltas[personal_account] = [
                        discount_fee_sum
                    ]

        # Удаляем помеченные транзакции из БД
        # self.logger.info(f'Удалить транзакции ГПН из локальной БД: {len(to_delete_local)} шт')
        # if to_delete_local:
        #     for transaction in to_delete_local:
        #         await self.delete_object(TransactionOrm, transaction.id)

        # Сообщаем о транзакциях, которые есть в БД, но нет в системе поставщика
        if to_delete_local:
            self.logger.error("В локальной БД присутствуют транзакции, "
                              f"которых нет в {self.system.short_name}: {to_delete_local}")

        # Транзакции от системы, оставшиеся необработанными, записываем в локальную БД.
        self.logger.info(f'Новые транзакции ГПН: {len(remote_transactions)} шт')
        if remote_transactions:
            await self.process_new_remote_transactions(remote_transactions)

        # Записываем в БД время последней успешной синхронизации
        await self.update_object(self.system, update_data={"transactions_sync_dt": datetime.now(tz=TZ)})

        # Обновляем время последней транзакции для карт
        await transaction_repository.renew_cards_date_last_use()

    @staticmethod
    def get_equal_remote_transaction(local_transaction: TransactionOrm, remote_transactions: List[Dict[str, Any]]) \
            -> Dict[str, Any] | None:
        for remote_transaction in remote_transactions:
            if str(remote_transaction['id']) == local_transaction.external_id:
                return remote_transaction

    async def process_new_remote_transactions(self, remote_transactions: List[Dict[str, Any]]) -> None:
        # Сортируем транзакции по времени совершения
        def sorting(tr):
            return tr['timestamp']

        remote_transactions = sorted(remote_transactions, key=sorting)

        # Подготавливаем список транзакций для сохранения в БД
        transactions_to_save = []
        for remote_transaction in remote_transactions:
            transaction_data = await self.process_new_remote_transaction(remote_transaction=remote_transaction)
            if transaction_data:
                transactions_to_save.append(transaction_data)
                self._irrelevant_balances.add(
                    balance_id=str(transaction_data['balance_id']),
                    irrelevancy_date_time=transaction_data['date_time_load']
                )

        # Сохраняем транзакции в БД
        await self.bulk_insert_or_update(TransactionOrm, transactions_to_save)

    async def process_new_remote_transaction(self, remote_transaction: Dict[str, Any]) \
            -> Dict[str, Any] | None:
        """Обработка транзакции, сохранение в БД. Примеры транзакций см. в файле transaction_examples.txt"""

        # Получаем продукт
        outer_goods = await self.get_outer_goods(goods_external_id=remote_transaction['product_id'])

        # Получаем АЗС
        azs = await self.get_azs(azs_external_id=remote_transaction['poi_id'])

        transaction_data = await self.helper.process_new_remote_transaction(
            card_number=remote_transaction['card_number'],
            outer_goods=outer_goods,
            azs=azs,
            irrelevant_balances=self._irrelevant_balances,
            purchase=True if remote_transaction['type'] == "P" else False,
            comments='',
            system_id=self.system.id,
            transaction_external_id=str(remote_transaction['id']),
            transaction_time=remote_transaction['timestamp'],
            transaction_sum=remote_transaction['sum_no_discount'],
            transaction_fuel_volume=remote_transaction['qty'],
            transaction_price=remote_transaction['price_no_discount']
        )

        return transaction_data

    async def get_outer_goods(self, goods_external_id: str) -> OuterGoodsOrm:
        outer_goods = await self.helper.get_outer_goods_item(goods_external_id=goods_external_id)
        if not outer_goods:
            # Если продукт не найден, то создаем его
            outer_goods_data = dict(
                external_id=goods_external_id,
                name=goods_external_id,
                system_id=self.system.id,
                inner_goods_id=None,
            )
            outer_goods = await self.insert(OuterGoodsOrm, **outer_goods_data)

        return outer_goods

    async def issue_virtual_cards(self, amount: int) -> List[str]:
        stmt = sa_select(CardTypeOrm).where(CardTypeOrm.name == "Виртуальная карта")
        card_type_virtual = await self.select_first(stmt)
        dataset = []
        for i in range(amount):
            remote_card = self.api.issue_virtual_card()
            local_card = CardOrm(
                card_number=remote_card['number'],
                card_type_id=card_type_virtual.id,
                external_id=remote_card['id'],
                is_active=False
            )
            await self.save_object(local_card)
            print(f'----- Кол-во выпущенных карт: {i + 1} -----')

        self.logger.info("Все новые виртуальные карты ГПН сохранены в локальную БД")
        card_numbers = [card['card_number'] for card in dataset]
        return card_numbers

    async def delete_card_limits(self, limit_ids: List[str]) -> None:
        for limit_id in limit_ids:
            self.api.delete_card_limit(limit_id=limit_id)

        # Удаление лимитов из БД в норме выполняется перед удалением из системы.
        # На данном этапе их уже не должно быть в БД. Но на всякий случай выполним "пустое" удаление.
        # Вдруг предшествующий код изменится в будущем.
        stmt = sa_delete(CardLimitOrm).where(CardLimitOrm.external_id.in_(limit_ids))
        await self.session.execute(stmt)
        await self.session.commit()

    async def import_azs(self) -> None:
        # Получаем из ГПН справочник стран
        gpn_countries = self.api.get_countries()

        # Получаем из ГПН справочник регионов
        gpn_regions = self.api.get_regions()

        # Получаем из БД список регионов
        tariff_repository = TariffRepository(session=self.session, user=None)
        regions = await tariff_repository.get_regions()
        local_region_names = [region.name for region in regions]

        # Формируем список новых регионов для записи в БД
        region_dataset = {}
        for region in gpn_regions:
            if region not in local_region_names:
                country_name = ""
                for country in gpn_countries:
                    if country["id"] == region["country_id"]:
                        country_name = country["value"]
                        break

                region_dataset[region["name"]] = country_name

        region_dataset = [{"name": region_name, "country": country} for region_name, country in region_dataset.items()]
        await self.bulk_insert_or_update(RegionOrm, region_dataset, "name")

        # Получаем из БД список регионов
        tariff_repository = TariffRepository(session=self.session, user=None)
        local_regions = await tariff_repository.get_regions()
        local_region_id_by_name = {region.name: region.id for region in local_regions}

        # Получаем из ГПН список АЗС
        stations = self.api.get_stations()

        def get_local_region(region_code: str) -> str | None:
            # Из справочника ГПН получаем имя региона
            region_name = ""
            for gpn_region in gpn_regions:
                if gpn_region["id"] == region_code:
                    region_name = gpn_region["name"]
                    break

            # Из локального справочника получаем ID региона
            return local_region_id_by_name.get(region_name, None)

        def get_own_type(system_own_type: str) -> AzsOwnType:
            if system_own_type.upper() == 'EXT':
                return AzsOwnType.PARTNER
            elif system_own_type.upper() == 'FRAN':
                return AzsOwnType.FRANCHISEE
            elif system_own_type.upper() == 'OPTI':
                return AzsOwnType.OPTI
            else:
                return AzsOwnType.OWN

        def get_working_days(system_working_time: Dict[str, Any] | None) -> str | None:
            return system_working_time if system_working_time else None

        def get_address(system_address: Dict[str, Any] | None) -> str | None:
            return system_address if system_address else None

        def get_coordinate(coordinate: str) -> float:
            if coordinate.startswith("."):
                return float(coordinate[1:])
            else:
                return float(coordinate)

        azs_dataset = [
            {
                "system_id": self.system.id,
                "external_id": azs["siebelId"],
                "name": azs["contractName"],
                "code": azs["contractName"],
                "is_active": True if azs["status"] == "257" else False,
                "region_id": get_local_region(azs["regionCode"]),
                "address": get_address(azs["address"]),
                "own_type": get_own_type(azs["ownType"]),
                "latitude": get_coordinate(azs["latitude"]),
                "longitude": get_coordinate(azs["longitude"]),
                "timezone": azs["timeZone"],
                "working_time": get_working_days(azs["working_time"])
            } for azs in stations
        ]
        await self.bulk_insert_or_update(AzsOrm, azs_dataset, "external_id")

    async def get_azs(self, azs_external_id: str) -> AzsOrm:
        azs = await self.helper.get_azs(azs_external_id=azs_external_id)
        if azs:
            return azs

        # Если АЗС не найдена, то создаем её
        azs_fields = dict(
            system_id=self.system.id,
            external_id=azs_external_id,
            name=azs_external_id,
            is_active=True,
            address={}
        )
        azs = await self.insert(AzsOrm, **azs_fields)
        return azs

    def remote_card_groups(self) -> List[Dict[str, Any]]:
        if self.card_groups is None:
            self.card_groups = self.api.get_card_groups()

        return self.card_groups

    async def update_group_limits(
            self,
            gpn_group_limit_increase_deltas: Dict[personal_account_str, List[delta_sum_float]] = None,
            gpn_group_limit_decrease_deltas: Dict[personal_account_str, List[delta_sum_float]] = None
    ) -> None:

        if not gpn_group_limit_increase_deltas and not gpn_group_limit_decrease_deltas:
            self.logger.warning("Получен пустой список организаций для обновления групповых лимитов.")
            return None

        if gpn_group_limit_increase_deltas is None:
            gpn_group_limit_increase_deltas = {}

        if gpn_group_limit_decrease_deltas is None:
            gpn_group_limit_decrease_deltas = {}

        # Получаем из БД организации, у которых есть карты ГПН
        personal_accounts_set = {personal_account for personal_account in gpn_group_limit_increase_deltas.keys()}
        personal_accounts_set.update({personal_account for personal_account in gpn_group_limit_decrease_deltas.keys()})
        personal_accounts = list(personal_accounts_set)
        stmt = (
            sa_select(CompanyOrm)
            .options(
                selectinload(CompanyOrm.group_limits)
            )
            .options(
                contains_eager(CompanyOrm.card_groups)
            )
            .outerjoin(CardGroupOrm, and_(
                CompanyOrm.id == CardGroupOrm.company_id,
                CardGroupOrm.system_id == self.system.id
            ))
            .where(CompanyOrm.personal_account.in_(personal_accounts))
            .where(CardOrm.company_id == CompanyOrm.id)
            .where(CardSystemOrm.card_id == CardOrm.id)
            .where(CardSystemOrm.system_id == self.system.id)
            .order_by(CompanyOrm.personal_account)
        )
        # self.statement(stmt)
        companies: List[CompanyOrm] = await self.select_all(stmt)
        if not companies:
            self.logger.warning("Из БД получен пустой список организаций, работающих с системой ГПН. "
                                "Обновление карточных лимитов ГПН не требуется.")
            return None

        # Обрабатываем полученные задания на установку / изменение групповых лимитов
        for company in companies:
            try:
                await self._update_group_limits_by_delta_sums(
                    company=company,
                    limit_increase_delta_sums=gpn_group_limit_increase_deltas.get(company.personal_account, []),
                    limit_decrease_delta_sums=gpn_group_limit_decrease_deltas.get(company.personal_account, [])
                )
            except Exception:
                self.logger.exception(f"Ошибка установки группового лимита ГПН организации {company.name}, "
                                      f"ЛС: {company.personal_account}")

    async def create_group_limits(self, company_id: str, company_name: str, personal_account: str,
                                  card_group_external_id: str, available_balance: float) -> None:
        # Получаем идентификатор карточной группы ГПН, сохраненный в БД

        # Создаем лимиты в ГПН на все категории продуктов
        local_limits_dataset = []
        for gpn_category in GpnGoodsCategory:
            limit_sum = max(int(math.floor(available_balance)), 1) if gpn_category == GpnGoodsCategory.FUEL else 1

            # Создаем лимит в ГПН
            remote_limit_id = self._set_group_limit(
                limit_id=None,
                group_id=card_group_external_id,
                gpn_goods_category=gpn_category,
                limit_sum=limit_sum,
                company_name=company_name,
                personal_account=personal_account,
                previous_remote_limit_sum=None,
                previous_remote_available_sum=None
            )
            if not remote_limit_id:
                raise CeleryError("Не удалось создать групповой лимит ГПН")

            # Запоминаем параметры лимита для последующей записи в локальную БД
            local_limits_dataset.append({
                "system_id": self.system.id,
                "external_id": remote_limit_id,
                "company_id": company_id,
                "limit_sum": limit_sum,
                "inner_goods_category": gpn_category.value["local_category"]
            })

        # Записываем созданные лимиты в локальную БД
        if local_limits_dataset:
            await self.bulk_insert_or_update(GroupLimitOrm, local_limits_dataset)

    async def _update_group_limits_by_delta_sums(self, company: CompanyOrm, limit_increase_delta_sums: List[float],
                                                 limit_decrease_delta_sums: List[float]) -> None:
        # Получаем идентификатор карточной группы ГПН, сохраненный в БД
        group_external_id = company.card_groups[0].external_id

        # Получаем информацию по каким категориям установлены лимиты на картах клиента
        card_repository = CardRepository(session=self.session)
        card_limit_categories = await card_repository.get_card_limit_categories(
            company_id=company.id,
            system_id=self.system.id
        )

        group_limit_categories_to_update = set(card_limit_categories)
        group_limit_categories_to_update.add(GoodsCategory.FUEL)

        for group_limit in company.group_limits:
            if group_limit.inner_goods_category in group_limit_categories_to_update:
                # Вычисляем новое значение лимита
                group_limit_sum = group_limit.limit_sum if group_limit.limit_sum > 1 else 0
                new_sum = group_limit_sum + sum(limit_increase_delta_sums) - sum(limit_decrease_delta_sums)
                group_limit.limit_sum = max(int(math.floor(new_sum)), 1)

                self.logger.info(f"Получены дельты сумм для изменения группового лимита организации {company.name}, "
                                 f"ЛС: {company.personal_account}, "
                                 f"дельты на добавление к лимиту: ({limit_increase_delta_sums}), "
                                 f"дельты на вычитание из лимита: ({limit_decrease_delta_sums}), ")

                # Обновляем лимит в ГПН
                limit_external_id = self._set_group_limit(
                    limit_id=group_limit.external_id,
                    group_id=group_external_id,
                    gpn_goods_category=GpnGoodsCategory.get_equal_by_local(group_limit.inner_goods_category),
                    limit_sum=group_limit.limit_sum,
                    company_name=company.name,
                    personal_account=company.personal_account,
                    previous_remote_limit_sum=None,
                    previous_remote_available_sum=None
                )
                if not limit_external_id:
                    # В ГПН не обнаружен лимит с таким идентификатором. Пробуем пересоздать лимит.
                    limit_external_id = self._set_group_limit(
                        limit_id=None,
                        group_id=group_external_id,
                        gpn_goods_category=GpnGoodsCategory.get_equal_by_local(group_limit.inner_goods_category),
                        limit_sum=group_limit.limit_sum,
                        company_name=company.name,
                        personal_account=company.personal_account,
                        previous_remote_limit_sum=None,
                        previous_remote_available_sum=None
                    )
                    if not limit_external_id:
                        await self.save_object(group_limit)
                        raise CeleryError("Не удалось установить лимит ГПН")

                    group_limit.external_id = limit_external_id

                await self.save_object(group_limit)

    async def update_group_limit_by_card_limit(self, company_id: str, card_limit_goods_category: GoodsCategory) \
            -> None:
        # Получаем организацию
        company_repository = CompanyRepository(session=self.session)
        company = await company_repository.get_company(company_id)

        # Получаем идентификатор карточной группы ГПН
        group = company.get_card_group(System.GPN.value)

        # Получаем размер установленного группового лимита на категорию "Топливо"
        group_fuel_limit: List[GroupLimitOrm] = list(filter(
            lambda local_limit: local_limit.inner_goods_category == GoodsCategory.FUEL,
            company.group_limits
        ))
        group_fuel_limit: GroupLimitOrm | None = group_fuel_limit[0] if group_fuel_limit else None

        # Если в локальной БД нет записи о групповом лимите на категорию Топливо, то это исключительная ситуация
        if not group_fuel_limit:
            raise CeleryError(f"В БД не обнаружен групповой лимит на категорию Топливо для организации "
                              f"{company.name}, personal_account = {company.personal_account}")

        # Сверяем лимиты по категориям, переданным в функцию. Если лимит не равен лимиту на категорию "Топливо",
        # то обновляем его.
        for limit in company.group_limits:
            if limit.inner_goods_category == card_limit_goods_category \
                    and limit.limit_sum != group_fuel_limit.limit_sum:

                limit.limit_sum = group_fuel_limit.limit_sum

                # Обновляем лимит в ГПН
                limit_external_id = self._set_group_limit(
                    limit_id=limit.external_id,
                    group_id=group.external_id,
                    gpn_goods_category=GpnGoodsCategory.get_equal_by_local(limit.inner_goods_category),
                    limit_sum=group_fuel_limit.limit_sum,
                    company_name=company.name,
                    personal_account=company.personal_account,
                    previous_remote_limit_sum=None,
                    previous_remote_available_sum=None
                )
                if not limit_external_id:
                    # Пробуем пересоздать лимит
                    limit_external_id = self._set_group_limit(
                        limit_id=None,
                        group_id=group.external_id,
                        gpn_goods_category=GpnGoodsCategory.get_equal_by_local(limit.inner_goods_category),
                        limit_sum=group_fuel_limit.limit_sum,
                        company_name=company.name,
                        personal_account=company.personal_account,
                        previous_remote_limit_sum=None,
                        previous_remote_available_sum=None
                    )
                    if not limit_external_id:
                        await self.save_object(limit)
                        raise CeleryError("Не удалось установить лимит ГПН")

                    limit.external_id = limit_external_id

                await self.save_object(limit)
                self.logger.info(f"В БД по организации {company.name} {company.personal_account} установлен "
                                 f"лимит {limit.limit_sum} р. на категорию {limit.inner_goods_category.name}")

    async def create_company(self, company_id: str, company_name: str, personal_account: str,
                             available_balance: float) -> str:
        # Создаем карточную группу в ГПН
        try:
            group_id = self.api.create_card_group(personal_account)

        except Exception:
            self.logger.error(
                f"Не удалось создать карточную группа в ГПН для организации {company_name} {personal_account}"
            )

        else:
            # Создаем карточную группу в БД
            local_card_group = CardGroupOrm(
                system_id=self.system.id,
                external_id=group_id,
                name=personal_account,
                company_id=company_id
            )
            await self.save_object(local_card_group)

            # Создаем групповые лимиты
            await self.create_group_limits(
                company_id=company_id,
                company_name=company_name,
                personal_account=personal_account,
                card_group_external_id=group_id,
                available_balance=available_balance
            )

            return group_id

    async def binding_cards(self, card_numbers: List[str], previous_company_id: str, new_company_id: str) -> None:
        """Связывание / открепление карт с карточной группой ГПН. В функцию могут быть переданы карты других систем.
        Предполагается, что все карты привязаны к одной организации (либо не привязаны ни к какой)."""

        # Получаем карты, относящиеся к системе ГПН
        card_repository = CardRepository(session=self.session)
        cards = await card_repository.get_cards_by_filters(system_id=self.system.id, card_numbers=card_numbers)

        company_repository = CompanyRepository(session=self.session)

        # Отвязываем карты ГПН от старой группы
        if previous_company_id and cards:
            previous_company = await company_repository.get_company(previous_company_id)
            # Получаем идентификатор группы карт ГПН
            previous_card_group = previous_company.get_card_group(System.GPN.value)
            if previous_card_group:
                self.api.unbind_cards_from_group(
                    card_numbers=[card.card_number for card in cards],
                    card_external_ids=[card.external_id for card in cards],
                    group_id=previous_card_group.external_id
                )

        # Привязываем карты к новой группе
        if new_company_id:
            new_company = await company_repository.get_company(new_company_id)

            # Получаем идентификатор группы карт ГПН
            new_card_group = new_company.get_card_group(System.GPN.value)

            if new_card_group:
                group_id = new_card_group.external_id
            else:
                # Если группа не существует, это означает, что к организации впервые привязали карту ГПН.
                # В этом случае выполняем набор действий по созданию группы и назначению лимитов.
                new_company = await company_repository.get_company(new_company_id)
                available_balance = calc_available_balance(
                    current_balance=new_company.overbought_balance().balance,
                    min_balance=new_company.min_balance,
                    overdraft_on=new_company.overdraft_on,
                    overdraft_sum=new_company.overdraft_sum
                )
                group_id = await self.create_company(
                    company_id=new_company.id,
                    company_name=new_company.name,
                    personal_account=new_company.personal_account,
                    available_balance=available_balance
                )

            # Привязываем карты к группе
            self.api.bind_cards_to_group(
                card_numbers=[card.card_number for card in cards],
                card_external_ids=[card.external_id for card in cards],
                group_id=group_id
            )

    async def sync_card_states(self) -> None:
        # Получаем список карт из БД
        local_cards = await self.helper.get_local_cards()

        # Получаем карты из ГПН
        remote_cards = self.api.get_gpn_cards()

        if len(local_cards) != len(remote_cards):
            self.logger.warning(f"Количество карт в БД ({len(local_cards)} шт) "
                                f"не соответствует количеству карт в ГПН ({len(remote_cards)} шт).")

        # Сверяем состояния карт. Если отличаются, в ГПН делаем смену состояний.
        card_external_ids_to_activate = []
        card_external_ids_to_block = []
        for local_card in local_cards:
            found = False
            for remote_card in remote_cards:
                if local_card.card_number == remote_card["number"]:
                    found = True
                    remote_card_is_active = True if "locked" not in remote_card["status"].lower() else False
                    if local_card.is_active != remote_card_is_active:
                        local_state = "активна" if local_card.is_active else "заблокирована"
                        remote_state = "активна" if remote_card_is_active else "заблокирована"
                        company_info = f"{local_card.company.name}, {local_card.company.personal_account}" \
                            if local_card.company_id else "не присвоена"
                        self.logger.warning(f"Состояние карты {local_card.card_number} в БД не соответствует состоянию "
                                            f"в ГПН. В БД карта {local_state}, в ГПН {remote_state}. "
                                            f"Организация {company_info}.")

                        if local_card.is_active:
                            card_external_ids_to_activate.append(local_card.external_id)
                        else:
                            card_external_ids_to_block.append(local_card.external_id)

                    break

            if not found:
                self.logger.warning(f"Карта {local_card.card_number} присутствует в БД, но не найдена в ГПН.")

        # Устанавливаем состояние карт в ГПН
        if card_external_ids_to_activate:
            self.logger.info(f"В ГПН отправлен запрос на активацию карт: {len(card_external_ids_to_activate)} шт")
            self.api.activate_cards(card_external_ids_to_activate)
            self.logger.info("Выполнена активация карт в ГПН")

        if card_external_ids_to_block:
            self.logger.info(f"В ГПН отправлен запрос на блокировку карт: {len(card_external_ids_to_block)} шт")
            self.api.block_cards(card_external_ids_to_block)
            self.logger.info("Выполнена блокировка карт в ГПН")

        if not card_external_ids_to_activate and not card_external_ids_to_block:
            self.logger.info("Состояния карт в БД и ГПН идентичны.")

    def _set_group_limit(self, limit_id: str | None, group_id: str, gpn_goods_category: GpnGoodsCategory,
                         limit_sum: float | int, company_name: str, personal_account: str,
                         previous_remote_limit_sum: float | int | None,
                         previous_remote_available_sum: float | int | None) -> str | None:

        # В функцию, в числе прочего, передаются сведения о предыдущем лимите в ГПН. Это нужно для отладки.
        # При идеально работающей системе это действие не требуется.
        # Если сведения не переданы, то запрашиваем их в ГПН.
        if limit_id and (previous_remote_limit_sum is None or previous_remote_available_sum is None):
            remote_limits = self.api.get_card_group_limits(group_id=group_id)
            if remote_limits:
                for remote_limit in remote_limits:
                    if remote_limit["productType"] == gpn_goods_category.value["id"]:
                        previous_remote_limit_sum = remote_limit["sum"]["valus"]
                        previous_remote_available_sum = remote_limit["sum"]["valus"] - remote_limit["sum"]["used"]
            else:
                self.logger.error("Ошибка при получении групповых лимитов ГПН "
                                  f"организации {company_name} {personal_account}")
                previous_remote_limit_sum = "{не определено}"
                previous_remote_available_sum = "{не определено}"

        remote_limit_id = self.api.set_group_limit(
            limit_id=limit_id,
            group_id=group_id,
            product_category=gpn_goods_category,
            limit_sum=max(int(math.floor(limit_sum)), 1)
        )

        if remote_limit_id:
            fn_result = "Обновлен групповой лимит" if limit_id else "Создан групповой лимит"
        else:
            fn_result = "Ошибка при обновлении группового лимита" if limit_id \
                else "Ошибка при создании группового лимита"
        message = (
            f"{fn_result} {limit_sum} р. на категорию {gpn_goods_category.value['local_category'].value} для "
            f"организации {company_name}, ЛС: {personal_account}."
        )
        if limit_id:
            message += (f" Предыдущие значения: лимит - {previous_remote_limit_sum}, "
                        f"доступно - {previous_remote_available_sum}")

        self.logger.info(message)

        return remote_limit_id

    async def make_group_limits_check_report(self) -> None:
        personal_accounts = None

        """
        personal_accounts = (
            "0268158",  # Бахарева Галина Николаевна
            "2369858",  # ИП Носуленко Николай Владимирович
            "0747704",  # ООО ТСК "ПРОМЭС"
            "4042053",  # ООО "САРТРАНСАВТО"
            "2183818",  # ООО "НОВЫЕ ЛОГИСТИЧЕСКИЕ ТЕХНОЛОГИИ"
            "5161054",  # ООО "ЭНЕРГОРЕСУРС"
        )
        """

        # Получаем из БД организации, имеющие карты ГПН.
        # Присоединяем сведения о балансах, группе карт, групповых и карточных лимитах
        company_tbl = aliased(CompanyOrm, name="company_tbl")
        card_tbl = aliased(CardOrm, name="card_tbl")
        card_system_tbl = aliased(CardSystemOrm, name="card_system_tbl")
        company_has_gpn_card_subq = (
            sa_select(1)
            .where(company_tbl.id == card_tbl.company_id)
            .where(card_tbl.id == card_system_tbl.card_id)
            .where(card_system_tbl.system_id == self.system.id)
            .limit(1)
            .exists()
        )

        stmt = (
            sa_select(company_tbl)
            .where(company_has_gpn_card_subq)
            .options(
                load_only(
                    company_tbl.id,
                    company_tbl.name,
                    company_tbl.personal_account,
                    company_tbl.min_balance,
                    company_tbl.overdraft_on,
                    company_tbl.overdraft_sum
                )
            )
            .options(
                selectinload(company_tbl.balances)
            )
            .options(
                selectinload(company_tbl.card_groups.and_(CardGroupOrm.system_id == self.system.id))
                .joinedload(CardGroupOrm.system)
            )
            .options(
                selectinload(company_tbl.group_limits.and_(GroupLimitOrm.system_id == self.system.id))
                .joinedload(GroupLimitOrm.system)
            )
            .options(
                selectinload(company_tbl.cards)
                .selectinload(CardOrm.limits)
            )
            .order_by(company_tbl.name)
        )

        companies = await self.select_all(stmt)
        self.logger.info("Из БД получен список организаций, имеющих карты ГПН")

        transaction_repository = TransactionRepository(session=self.session)

        # Получаем из БД предыдущий отчет. Из него будем брать записи, если с момента генерации предыдущего отчета
        # не было транзакций по организации
        stmt = (
            sa_select(CheckReportOrm)
            .where(CheckReportOrm.report_type == CheckReport.GPN_GROUP_LIMITS)
            .order_by(desc(CheckReportOrm.creation_time))
            .limit(1)
        )
        previous_report: CheckReportOrm = await self.select_first(stmt)

        def get_company_data_from_previous_report(personal_account) -> Dict[str, Any]:
            for _company_data in previous_report.data:
                if _company_data["personal_account"] == personal_account:
                    return _company_data

        # Формируем данные отчета
        report_data = []
        i = 1
        companies_amount = len(companies)
        for company in companies:
            spaces = " " * (5 - len(str(i)))
            self.logger.info(f"{spaces}{i} из {companies_amount}. Формирую данные по организации {company.name}")
            i += 1
            if personal_accounts and company.personal_account not in personal_accounts:
                continue

            # Вычисляем доступный баланс
            overbought_balance = company.overbought_balance()
            available_balance = calc_available_balance(
                current_balance=company.overbought_balance().balance,
                min_balance=company.min_balance,
                overdraft_on=company.overdraft_on,
                overdraft_sum=company.overdraft_sum
            )

            # Получаем последнюю транзакцию
            last_transaction = await transaction_repository.get_last_transaction(balance_id=overbought_balance.id)

            # Если со времени последнего отчета не было транзакций, то берем данные из последнего отчета
            if (previous_report and
                    (not last_transaction
                     or last_transaction and previous_report.creation_time > last_transaction.date_time_load)):
                company_data = get_company_data_from_previous_report(company.personal_account)
                if company_data:
                    report_data.append(company_data)
                    self.logger.info("Использованы данные из предыдущего отчета")
                    continue

            # Из ГПН получаем сведения о групповых лимитах
            self.logger.info("Запрос данных из ГПН")
            card_group = company.get_card_group(System.GPN.value)
            remote_group_limits = self.api.get_card_group_limits(group_id=card_group.external_id) if card_group else []

            # Формируем структуру данных о лимитах организации
            group_limits = []
            for gpn_category in GpnGoodsCategory:
                # Локальный групповой лимит
                local_group_limit_sum = "Не установлен"
                for group_limit in company.group_limits:
                    if group_limit.inner_goods_category == gpn_category.value["local_category"]:
                        local_group_limit_sum = group_limit.limit_sum
                        break

                # Флаг наличия карточного лимита этой категории хотя бы по одной карте
                card_limit_flag = company.has_card_limit_with_certain_category(
                    system_id=self.system.id,
                    inner_goods_category=gpn_category.value["local_category"]
                )

                # Групповой лимит ГПН
                remote_group_limit_sum = "Не установлен"
                remote_group_limit_available_sum = "-"
                for remote_group_limit in remote_group_limits:
                    if remote_group_limit["productType"] == gpn_category.value["id"]:
                        remote_group_limit_sum = banking_round(remote_group_limit["sum"]["value"])
                        remote_group_limit_available_sum = banking_round(
                            remote_group_limit_sum - remote_group_limit["sum"]["used"]
                        )
                        break

                category_data = {
                    "category": gpn_category.value["local_category"].value,
                    "local_group_limit_sum": local_group_limit_sum,
                    "remote_group_limit_sum": remote_group_limit_sum,
                    "remote_group_limit_available_sum": remote_group_limit_available_sum,
                    "card_limit_flag": card_limit_flag,
                }
                group_limits.append(category_data)

            last_transaction_time = last_transaction.date_time_load.replace(microsecond=0).isoformat() \
                if last_transaction else ""
            company_data = {
                "company_name": company.name,
                "personal_account": company.personal_account,
                "balance": overbought_balance.balance,
                "last_transaction_time": last_transaction_time,
                "overdraft_on": company.overdraft_on,
                "overdraft_sum": company.overdraft_sum,
                "min_balance": company.min_balance,
                "available_balance": available_balance,
                "group_limits": group_limits
            }
            report_data.append(company_data)
            # break

        # Записываем отчет в БД
        user_repository = UserRepository(session=self.session)
        cargo_superadmin_role = await user_repository.get_role_by_name(Role.CARGO_SUPER_ADMIN.name)
        check_report = CheckReportOrm(
            report_type=CheckReport.GPN_GROUP_LIMITS,
            data=report_data,
            role_id=cargo_superadmin_role.id
        )
        await self.save_object(check_report)
