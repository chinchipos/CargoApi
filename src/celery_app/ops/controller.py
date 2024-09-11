import copy
import os
import time
from datetime import datetime
from typing import List, Dict, Any

from lxml import etree
from sqlalchemy.ext.asyncio import AsyncSession
from zeep.exceptions import Fault

from src.celery_app.exceptions import CeleryError
from src.celery_app.irrelevant_balances import IrrelevantBalances
from src.celery_app.ops.api import OpsApi
from src.celery_app.transaction_helper import get_local_cards, get_local_card
from src.config import TZ
from src.database.models import CardOrm, SystemOrm, CardSystemOrm, AzsOrm, TerminalOrm, OuterGoodsOrm, TransactionOrm, \
    TariffNewOrm, BalanceOrm, CompanyOrm, InnerGoodsGroupOrm
from src.database.models.card import BlockingCardReason, CardHistoryOrm
from src.repositories.azs import AzsRepository
from src.repositories.base import BaseRepository
from src.repositories.card import CardRepository
from src.repositories.card_type import CardTypeRepository
from src.repositories.goods import GoodsRepository
from src.repositories.system import SystemRepository
from src.repositories.tariff import TariffRepository
from src.repositories.transaction import TransactionRepository
from src.utils.enums import ContractScheme, System, TransactionType
from src.utils.loggers import get_logger


class OpsController(BaseRepository):

    def __init__(self, session: AsyncSession):
        super().__init__(session, None)
        self.logger = get_logger(name="OPSController", filename="celery.log")
        self.api = OpsApi()
        self.system = None
        self._irrelevant_balances = IrrelevantBalances(system=System.OPS)
        self._outer_goods_list: List[OuterGoodsOrm] = []
        self._card_history: List[CardHistoryOrm] = []
        self._terminals: List[TerminalOrm] = []
        self._tariffs: List[TariffNewOrm] = []
        self._local_cards: List[CardOrm] = []

    async def init_system(self) -> None:
        system_repository = SystemRepository(self.session)
        # Проверяем существование системы, если нет - создаем.
        self.system = await system_repository.get_system_by_short_name(
            short_name=System.OPS.value,
            scheme=ContractScheme.OVERBOUGHT
        )

        if not self.system:
            self.system = SystemOrm(
                full_name=System.OPS.value,
                short_name=System.OPS.value,
                scheme=ContractScheme.OVERBOUGHT
            )
            await self.save_object(self.system)

        if not self.system:
            raise CeleryError("В БД не найдена запись о системе", trace=False)

    async def load_cards(self) -> None:
        # self.api.show_wsdl_methods("Cards")
        self.logger.info("Начинаю импорт карт")
        try:
            start_time = datetime.now()

            # Получаем все карты из ОПС
            remote_cards = self.api.get_cards()

            # Получаем все карты из БД
            card_repository = CardRepository(session=self.session, user=None)
            local_cards = await card_repository.get_cards_by_filters(system_id=self.system.id)

            # Сравниваем списки. Одинаковые записи исключаем из обоих списков для уменьшения стоимости алгоритма.
            i = 0
            while i < len(remote_cards):
                remote_card = remote_cards[i]
                found = False
                for local_card in local_cards:
                    if local_card.card_number == remote_card["cardNumber"]:
                        found = True
                        local_cards.remove(local_card)
                        remote_cards.remove(remote_card)
                        break

                if not found:
                    i += 1

            # В списке локальных карт не должно остаться ни одной карты. Если это произошло, то что-то не в порядке.
            for local_card in local_cards:
                self.logger.error(f"Карта {local_card.card_number} присутствует в локальной БД, "
                                  f"но отсутствует в системе ОПС")

            # Карты, оставшиеся в списке ОПС - новые карты. Записываем их в БД.
            card_type_repository = CardTypeRepository(session=self.session, user=None)
            plastic_card_type = await card_type_repository.get_card_type(name="Пластиковая карта")
            if not plastic_card_type:
                raise CeleryError("В БД не найден тип карты [Пластиковая карта]", trace=False)

            new_cards_dataset = [
                {
                    "card_number": remote_card["cardNumber"],
                    "card_type_id": plastic_card_type.id,
                    "is_active": True if remote_card["cardStateID"] == 0 else False,
                } for remote_card in remote_cards
            ]
            await self.bulk_insert_or_update(CardOrm, new_cards_dataset, "card_number")

            # Получаем вновь созданные карты из БД.
            new_cards = await card_repository.get_cards_by_filters(
                card_numbers=[card["card_number"] for card in new_cards_dataset]
            )

            # Привязываем карты к системе
            card_system_dataset = [
                {
                    "card_id": card.id,
                    "system_id": self.system.id
                } for card in new_cards
            ]
            await self.bulk_insert_or_update(CardSystemOrm, card_system_dataset)

            # Получаем вновь созданные карты из БД с заблокированным статусом
            blocked_remote_cards = [remote_card for remote_card in remote_cards
                                    if remote_card["cardStateID"] in [4, 6, "4", "6"]]
            if blocked_remote_cards:
                new_cards = await card_repository.get_cards_by_filters(
                    card_numbers=[remote_card["cardNumber"] for remote_card in blocked_remote_cards]
                )

                # Записываем причину блокировки карты, если таковая имела место
                for new_card in new_cards:
                    for remote_card in blocked_remote_cards:
                        if new_card.card_number == remote_card["cardNumber"]:
                            if remote_card["cardStateID"] == 4:
                                new_card.reason_for_blocking = BlockingCardReason.COMPANY
                            elif remote_card["cardStateID"] == 6:
                                new_card.reason_for_blocking = BlockingCardReason.PIN
                            await self.save_object(new_card)
                            blocked_remote_cards.remove(remote_card)
                            break

            end_time = datetime.now()
            self.logger.info(f'Прогрузка карт завершена. Время выполнения: {str(end_time - start_time).split(".")[0]}. '
                             f'Количество новых карт: {len(new_cards_dataset)}')

        except Fault as e:
            text = f"---------------------{os.linesep}"
            text += f"{e.message}{os.linesep}"

            hist = self.api.history.last_sent
            text += f"---------------------{os.linesep}"
            text += f"{etree.tostring(hist["envelope"], encoding="unicode", pretty_print=True)}"

            hist = self.api.history.last_received
            text += f"---------------------{os.linesep}"
            text += f"{etree.tostring(hist["envelope"], encoding="unicode", pretty_print=True)}"

    async def sync(self) -> IrrelevantBalances:
        # Прогружаем новые карты
        # await self.load_cards()

        # Прогружаем транзакции
        await self.load_transactions()

        # Прогружаем АЗС
        # await self.load_azs()

        # Прогружаем продукты
        # await self.load_goods()

        return self._irrelevant_balances

    async def load_azs(self) -> None:
        # self.api.show_wsdl_methods("Terminals")
        self.logger.info("Начинаю прогрузку АЗС")
        start_time = datetime.now()

        # Получаем список АЗС от системы ОПС
        remote_terminals = self.api.get_terminals()
        self.logger.info(f'Количество терминалов от системы ОПС: {len(remote_terminals)} шт')

        remote_stations = {}
        for remote_terminal in remote_terminals:
            azs_external_id = remote_terminal["servicePointID"]
            if azs_external_id not in remote_stations:
                remote_stations[azs_external_id] = {
                    "external_id": azs_external_id,
                    "name": remote_terminal["servicePointName"],
                    "address": remote_terminal["servicePointAddress"],
                }
        self.logger.info(f'Количество АЗС от системы ОПС: {len(remote_stations)} шт')

        # Получаем список АЗС из локальной БД
        azs_repository = AzsRepository(session=self.session, user=None)
        local_stations = await azs_repository.get_stations(system_id=self.system.id)
        self.logger.info(f'Количество АЗС в локальной БД: {len(local_stations)} шт')

        # Сравниваем списки АЗС. Одинаковые записи исключаем из обоих списков для уменьшения стоимости алгоритма.
        i = 0
        while i < len(local_stations):
            local_station = local_stations[i]
            if local_station.external_id in remote_stations:
                remote_stations.pop(local_station.external_id)
                local_stations.remove(local_station)
                i += 1

        # Если в локальном списке АЗС остались записи, то помечаем эти АЗС как неактивные.
        self.logger.info(f"Количество АЗС, сменивших статус на неактивный: {len(local_stations)} шт")
        azs_dataset = [{"id": azs.id, "is_active": False} for azs in local_stations]
        await self.bulk_update(AzsOrm, azs_dataset)

        # АЗС, оставшиеся в списке ОПС - новые АЗС. Записываем их в БД.
        new_stations_dataset = [
            {
                "system_id": self.system.id,
                "external_id": remote_station["external_id"],
                "name": remote_station["name"],
                "code": remote_station["name"],
                "address": remote_station["address"],
            } for azs_external_id, remote_station in remote_stations.items()
        ]
        await self.bulk_insert_or_update(AzsOrm, new_stations_dataset)
        self.logger.info(f"Количество новых АЗС: {len(new_stations_dataset)} шт")

        # Получаем список терминалов из локальной БД
        local_terminals = await azs_repository.get_terminals(system_id=self.system.id)
        self.logger.info(f'Количество терминалов в локальной БД: {len(local_terminals)} шт')

        # Сравниваем списки терминалов. Одинаковые записи исключаем из обоих списков для уменьшения стоимости алгоритма.
        i = 0
        while i < len(remote_terminals):
            remote_terminal = remote_terminals[i]
            found = False
            for local_terminal in local_terminals:
                if local_terminal.external_id == remote_terminal["terminalID"]:
                    found = True
                    if local_terminal.azs.external_id != remote_terminal["servicePointID"]:
                        # Терминал ранее принадлежал другой АЗС. Перемещаем его.
                        local_azs = await azs_repository.get_station_by_external_id(
                            external_id=remote_terminal["servicePointID"]
                        )
                        local_terminal.azs_id = local_azs.id
                        await self.save_object(local_terminal)

                    remote_terminals.remove(remote_terminal)
                    local_terminals.remove(local_terminal)
                    break

            if not found:
                i += 1

        # Записываем в БД новые терминалы
        local_stations = await azs_repository.get_stations(system_id=self.system.id)
        local_stations = {azs.external_id: azs.id for azs in local_stations}
        terminal_dataset = [
            {
                "external_id": remote_terminal["terminalID"],
                "name": remote_terminal["terminalName"],
                "azs_id": local_stations[remote_terminal["servicePointID"]]
            } for remote_terminal in remote_terminals
        ]
        await self.bulk_insert_or_update(TerminalOrm, terminal_dataset)
        self.logger.info(f"Количество новых терминалов: {len(terminal_dataset)} шт")

        end_time = datetime.now()
        self.logger.info(f'Прогрузка АЗС завершена. Время выполнения: {str(end_time - start_time).split(".")[0]}.')

    async def load_transactions(self) -> None:
        # self.api.show_wsdl_methods("TransactionReceipts")
        self.logger.info("Начинаю прогрузку транзакций")

        # Получаем список транзакций от поставщика услуг
        remote_transactions = self.api.get_transactions(transaction_days=self.system.transaction_days)
        self.logger.info(f'Количество транзакций от системы ОПС: {len(remote_transactions)} шт')

        if not len(remote_transactions):
            return None

        # Получаем список транзакций из локальной БД
        transaction_repository = TransactionRepository(self.session)
        local_transactions = await transaction_repository.get_recent_system_transactions(
            system_id=self.system.id,
            transaction_days=self.system.transaction_days
        )
        self.logger.info(f'Количество транзакций из локальной БД: {len(local_transactions)} шт')

        # Сравниваем транзакции локальные с полученными от системы.
        # Идентичные транзакции исключаем из списков.
        self.logger.info('Приступаю к процедуре сравнения локальных транзакций с полученными от системы ОПС')
        to_delete_local = []
        for local_transaction in local_transactions:
            remote_transaction = self.get_equal_remote_transaction(local_transaction, remote_transactions)
            if remote_transaction:
                remote_transactions.remove(remote_transaction)
            else:
                # Транзакция присутствует локально, но в системе поставщика её нет.
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
                if personal_account in self._irrelevant_balances.sum_deltas:
                    self._irrelevant_balances.sum_deltas[personal_account] -= local_transaction.total_sum
                else:
                    self._irrelevant_balances.sum_deltas[personal_account] = local_transaction.total_sum

        # Удаляем помеченные транзакции из БД
        self.logger.info(f'Удалить тразакции из локальной БД: {len(to_delete_local)} шт')
        if to_delete_local:
            for transaction in to_delete_local:
                await self.delete_object(TransactionOrm, transaction.id)

        # Транзакции от системы, оставшиеся необработанными, записываем в локальную БД.
        self.logger.info(f'Новые тразакции от системы ОПС: {len(remote_transactions)} шт')
        if remote_transactions:
            await self.process_new_remote_transactions(remote_transactions, transaction_repository)

        # Записываем в БД время последней успешной синхронизации
        await self.update_object(self.system, update_data={"transactions_sync_dt": datetime.now(tz=TZ)})

        # Обновляем время последней транзакции для карт
        await transaction_repository.renew_cards_date_last_use()

    @staticmethod
    def get_equal_remote_transaction(local_transaction: TransactionOrm, remote_transactions: List[Dict[str, Any]]) \
            -> Dict[str, Any] | None:
        for remote_transaction in remote_transactions:
            if remote_transaction['transactionID'] == local_transaction.external_id:
                return remote_transaction

    async def process_new_remote_transactions(self, remote_transactions: List[Dict[str, Any]],
                                              transaction_repository: TransactionRepository) -> None:

        # Получаем список продуктов / услуг
        self._outer_goods_list = await transaction_repository.get_outer_goods_list(system_id=self.system.id)

        # Получаем историю принадлежности карт
        card_repository = CardRepository(session=self.session, user=None)
        self._card_history = copy.deepcopy(await card_repository.get_card_history())

        # Получаем список АЗС
        azs_repository = AzsRepository(session=self.session)
        self._terminals = copy.deepcopy(await azs_repository.get_terminals(self.system.id))

        # Получаем тарифы
        tariff_repository = TariffRepository(session=self.session)
        self._tariffs = copy.deepcopy(await tariff_repository.get_tariffs(system_id=self.system.id))

        # Получаем карты
        card_numbers = [transaction['cardNumber'] for transaction in remote_transactions]
        self._local_cards = await get_local_cards(
            session=self.session,
            system_id=self.system.id,
            card_numbers=card_numbers
        )

        # Подготавливаем список транзакций для сохранения в БД
        transactions_to_save = []
        for remote_transaction in remote_transactions:
            transaction_data = await self.process_new_remote_transaction(
                remote_transaction=remote_transaction
            )
            if transaction_data:
                transactions_to_save.append(transaction_data)
                # if transaction_data['balance_id']:
                self._irrelevant_balances.add(
                    balance_id=str(transaction_data['balance_id']),
                    irrelevancy_date_time=transaction_data['date_time_load']
                )

        # Сохраняем транзакции в БД
        await self.bulk_insert_or_update(TransactionOrm, transactions_to_save)

    async def process_new_remote_transaction(self, remote_transaction: Dict[str, Any]) \
            -> Dict[str, Any] | None:
        """
        Обработка транзакции, сохранение в БД. Примеры транзакций см. в файле transaction_examples.txt
        """
        """
        {
            'transactionID': '100000100000000000099522842',
            'transactionDateTime': '2024-08-12 16:42:26',
            'terminalID': 59945,
            'cardNumber': 7801310000000000017,
            'contractID': 811091,
            'contractType': 2,
            'clientID': 790995,
            'contractOwnerID': 103,
            'transactionType': 0,
            'receiptItem': {
                'item': [
                    {
                        'position': 1,
                        'goodsID': 73916,
                        'paymentType': 5,
                        'priceWithoutDiscount': 58.07,
                        'price': 58.07,
                        'quantity': 5.0,
                        'amountWithoutDiscountRounded': 290.35,
                        'amountRounded': 290.35
                    }
                ]
            },
            'receiptDiscount': 0.0,
            'totalTransactionAmount': 290.35,
            'costVGItems': None
        }
        """

        purchase = True if remote_transaction['transactionType'] == 0 else False
        comments = ''

        # Получаем карту
        card = await get_local_card(remote_transaction["cardNumber"], self._local_cards)

        # Получаем баланс
        company = self.get_company_by_card_number(card_number=remote_transaction["cardNumber"])
        balance = company.overbought_balance()

        # Получаем продукт
        outer_goods = await self.get_outer_goods(remote_transaction)

        # Получаем АЗС
        azs = await self.get_azs(terminal_external_id=remote_transaction["terminalID"])

        # Получаем тариф
        tariff = self.get_company_tariff_on_transaction_time(
            company=balance.company,
            transaction_time=remote_transaction["transactionDateTime"],
            inner_group=outer_goods.outer_group.inner_group if outer_goods.outer_group else None,
            azs=azs
        )
        if not tariff:
            self.logger.error(f"Не удалось определить тариф для транзакции {remote_transaction}")

        # Сумма транзакции
        transaction_type = TransactionType.PURCHASE if purchase else TransactionType.REFUND
        transaction_sum = -abs(remote_transaction["amountWithoutDiscountRounded"]) if purchase \
            else abs(remote_transaction["amountWithoutDiscountRounded"])

        # Сумма скидки/наценки
        discount_fee_percent = tariff.discount_fee / 100 if tariff else 0
        discount_fee_sum = transaction_sum * discount_fee_percent

        # Получаем итоговую сумму
        total_sum = transaction_sum + discount_fee_sum

        transaction_data = dict(
            external_id=str(remote_transaction["transactionID"]),
            date_time=remote_transaction["transactionDateTime"],
            date_time_load=datetime.now(tz=TZ),
            transaction_type=transaction_type,
            system_id=self.system.id,
            card_id=card.id,
            balance_id=balance.id,
            azs_code=azs.external_id,
            outer_goods_id=outer_goods.id if outer_goods else None,
            fuel_volume=-remote_transaction["quantity"],
            price=remote_transaction["priceWithoutDiscount"],
            transaction_sum=transaction_sum,
            tariff_new_id=tariff.id if tariff else None,
            discount_sum=discount_fee_sum if discount_fee_percent < 0 else 0,
            fee_sum=discount_fee_sum if discount_fee_percent > 0 else 0,
            total_sum=total_sum,
            company_balance_after=0,
            comments=comments,
        )

        # Вычисляем дельту изменения суммы баланса - понадобится позже для правильного
        # выставления лимита на группу карт
        if company.personal_account in self._irrelevant_balances.sum_deltas:
            self._irrelevant_balances.sum_deltas[company.personal_account] += transaction_data["total_sum"]
        else:
            self._irrelevant_balances.sum_deltas[company.personal_account] = transaction_data["total_sum"]

        # Это нужно, чтобы в БД у транзакций отличалось время и можно было корректно выбрать транзакцию,
        # которая предшествовала измененной
        time.sleep(0.001)

        return transaction_data

    def get_company_by_card_number(self, card_number: str) -> CompanyOrm | None:
        card = None
        company = None
        for record in self._card_history:
            if record.card.card_number == card_number:
                card = record.card
                company = record.company

        return company if company else card.company

    async def get_outer_goods(self, remote_transaction: Dict[str, Any]) -> OuterGoodsOrm:
        product_id = remote_transaction['goodsID']
        # Выполняем поиск продукта в локальной БД
        for goods in self._outer_goods_list:
            if goods.external_id == product_id:
                return goods

        # Если продукт не найден, то запрашиваем о нем сведения у API
        goods = self.api.get_goods(product_id)
        fields = dict(
            external_id=product_id,
            system_id=self.system.id,
            inner_goods_id=None,
        )
        fields["name"] = goods[0]["goodsName"] if goods else product_id
        goods = await self.insert(OuterGoodsOrm, **fields)
        self._outer_goods_list.append(goods)
        return goods

    async def get_azs(self, terminal_external_id: str) -> AzsOrm:
        # Выполняем поиск АЗС
        for terminal in self._terminals:
            if terminal.external_id == terminal_external_id:
                return terminal.azs

        # Если АЗС не найдена, то запрашиваем о ней сведения у API
        terminals = self.api.get_terminals(terminal_external_id)
        if not terminals:
            raise CeleryError(f"Не удалось определить АЗС по идентификатору терминала {terminal_external_id}")

        # Выполняем поиск АЗС
        azs = None
        azs_external_id = terminals[0]["servicePointID"]
        for terminal in self._terminals:
            if terminal.azs.external_id == azs_external_id:
                azs = terminal.azs

        # Сохраняем запись об АЗС
        if not azs:
            azs_fields = dict(
                system_id=self.system.id,
                external_id=azs_external_id,
                name=terminals[0]["servicePointName"],
                code=terminals[0]["servicePointName"],
                address=terminals[0]["servicePointAddress"],
            )
            azs = await self.insert(AzsOrm, **azs_fields)

        # Сохраняем запись о терминале
        terminal_fields = dict(
            external_id=terminals[0]["terminalID"],
            name=terminals[0]["terminalName"],
            azs_id=azs.id,
        )
        terminal: TerminalOrm = await self.insert(TerminalOrm, **terminal_fields)

        terminal.annotate({"azs": azs})
        self._terminals.append(terminal)
        return azs

    def get_company_tariff_on_transaction_time(self, company: CompanyOrm, transaction_time: datetime,
                                               inner_group: InnerGoodsGroupOrm | None, azs: AzsOrm | None) \
            -> TariffNewOrm:
        # Получаем список тарифов, действовавших для компании на момент совершения транзакции
        tariffs = []
        # print('111111111111111111111111')
        # print(len(self._tariffs))
        for tariff in self._tariffs:
            # print('222222222222222222222222')
            # print(f"policy_id: {tariff.policy_id} | {company.tariff_policy_id} | {tariff.policy_id == company.tariff_policy_id}")
            # print(f"policy_id: {tariff.begin_time} | {transaction_time} | {tariff.begin_time <= transaction_time}")
            # print(f"end_time: {tariff.end_time} | {transaction_time} | {(tariff.end_time and tariff.end_time > transaction_time) or not tariff.end_time}")
            if tariff.policy_id == company.tariff_policy_id and tariff.begin_time <= transaction_time:
                if (tariff.end_time and tariff.end_time > transaction_time) or not tariff.end_time:
                    tariffs.append(tariff)

        # print('33333333333333333333333333')
        # print(f"tariffs length: {len(tariffs)}")
        # Перебираем тарифы и применяем первый подошедший
        for tariff in tariffs:
            # АЗС
            # print(f"azs_id: {tariff.azs_id} | {azs.id} | {tariff.azs_id and tariff.azs_id != azs.id}")
            if tariff.azs_id and tariff.azs_id != azs.id:
                # print('continue')
                continue

            # Тип АЗС
            # print(f"azs_own_type: {tariff.azs_own_type} | {azs.own_type} | "
            #       f"{tariff.azs_own_type and tariff.azs_own_type != azs.own_type}")
            if tariff.azs_own_type and tariff.azs_own_type != azs.own_type:
                # print('continue')
                continue

            # Регион
            # print(f"region_id: {tariff.region_id} | {azs.region_id} | "
            #       f"{tariff.region_id and tariff.region_id != azs.region_id}")
            if tariff.region_id and tariff.region_id != azs.region_id:
                # print('continue')
                continue

            # Группа продуктов
            # print(f"inner_goods_group_id: {tariff.inner_goods_group_id} | {inner_group.id if inner_group else None} | "
            #       f"{tariff.inner_goods_group_id and inner_group and tariff.inner_goods_group_id != inner_group.id}")
            if tariff.inner_goods_group_id and inner_group and tariff.inner_goods_group_id != inner_group.id:
                # print('continue')
                continue

            # Категория продуктов
            # print(f"inner_goods_category: {tariff.inner_goods_category} | "
            #       f"{inner_group.inner_category if inner_group else None}")
            if tariff.inner_goods_category and inner_group and \
                    tariff.inner_goods_category != inner_group.inner_category:
                # print('continue')
                continue

            # Тариф удовлетворяет критериям - возвращаем его
            return tariff

    async def load_goods(self) -> None:
        self.api.show_wsdl_methods("Goods")
        self.logger.info("Начинаю прогрузку продуктов")
        start_time = datetime.now()

        # Получаем список продуктов от системы ОПС
        remote_goods = self.api.get_goods()
        self.logger.info(f'Количество продуктов от системы ОПС: {len(remote_goods)} шт')

        # Получаем список продуктов из локальной БД
        goods_repository = GoodsRepository(session=self.session)
        local_goods = await goods_repository.get_outer_goods(system_id=self.system.id)
        local_goods = [goods.external_id for goods in local_goods if goods.external_id]
        self.logger.info(f'Количество продуктов в локальной БД: {len(local_goods)} шт')

        # Сравниваем списки
        i = 0
        while i < len(remote_goods):
            remote_goods_item = remote_goods[i]
            found = False
            if remote_goods_item["goodsID"] in local_goods:
                found = True
                remote_goods.remove(remote_goods_item)
                local_goods.remove(remote_goods_item["goodsID"])

            if not found:
                i += 1

        # Записываем в БД новые продукты
        goods_dataset = [
            {
                "external_id": goods["goodsID"],
                "name": goods["goodsName"],
                "system_id": self.system.id
            } for goods in remote_goods
        ]
        await self.bulk_insert_or_update(OuterGoodsOrm, goods_dataset)
        self.logger.info(f"Количество новых продуктов: {len(goods_dataset)} шт")

        end_time = datetime.now()
        self.logger.info('Прогрузка продуктов завершена. Время выполнения: '
                         f'{str(end_time - start_time).split(".")[0]}.')