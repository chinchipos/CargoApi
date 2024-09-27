import os
import time
from datetime import datetime
from src.config import TZ
from logging import Logger
from typing import List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.celery_app.exceptions import CeleryError
from src.celery_app.irrelevant_balances import IrrelevantBalances
from src.database.models import CardOrm, CompanyOrm, InnerGoodsGroupOrm, AzsOrm, TariffNewOrm, CardHistoryOrm, \
    OuterGoodsOrm
from src.repositories.azs import AzsRepository
from src.repositories.base import BaseRepository
from src.repositories.card import CardRepository
from src.repositories.goods import GoodsRepository
from src.repositories.tariff import TariffRepository
from src.utils.common import banking_round
from src.utils.enums import TransactionType


class TransactionHelper(BaseRepository):

    def __init__(self, session: AsyncSession, logger: Logger, system_id: str = None):
        super().__init__(session, None)
        self.logger = logger
        self._cards_history: List[CardHistoryOrm] | None = None
        self.system_id = system_id

        self._azs_repository: AzsRepository = AzsRepository(session=session)
        self._goods_repository: GoodsRepository = GoodsRepository(session=session)
        self._card_repository: CardRepository = CardRepository(session=session)
        self._tariff_repository: TariffRepository = TariffRepository(session=session)
        self._card_repository: CardRepository = CardRepository(session=session)

    async def get_local_cards(self, card_numbers: List[str] | None = None) -> List[CardOrm]:
        card_repository = CardRepository(session=self.session, user=None)
        local_cards = await card_repository.get_cards_by_filters(
            system_id=self.system_id,
            card_numbers=card_numbers
        )
        return local_cards

    @staticmethod
    def get_local_card(card_number, local_cards: List[CardOrm]) -> CardOrm:
        for card in local_cards:
            if card.card_number == card_number:
                return card

        raise CeleryError(trace=True, message=f'Карта с номером {card_number} не найдена в БД')

    async def get_probable_tariffs(self, tariff_policy_id: str, system_id: str, transaction_time: datetime) \
            -> List[TariffNewOrm]:
        tariffs = await self._tariff_repository.get_probable_tariffs_for_transaction(
            tariff_policy_id=tariff_policy_id,
            system_id=system_id,
            transaction_time=transaction_time
        )
        return tariffs

    async def get_card_company_on_time(self, card: CardOrm, _time: datetime) -> CompanyOrm:
        company = await self._card_repository.get_card_company_on_time(card.card_number, _time)
        if company:
            return company

        self.logger.error(f"В истории карт не найдена запись кто владел картой {card.card_number} "
                          f"на указанное время {_time.isoformat()}")

        # Получаем карту, отдаем текущего владельца карты
        if card.company_id and card.company:
            return card.company

        raise CeleryError(f"Не удалось определить организацию для карты {card.card_number}")

    async def get_outer_goods_item(self, goods_external_id: str) -> OuterGoodsOrm | None:
        outer_goods = await self._goods_repository.get_outer_goods_item(outer_goods_external_id=goods_external_id)
        return outer_goods

    async def get_azs(self, azs_external_id: str = None, terminal_external_id: str = None) -> AzsOrm:
        if azs_external_id:
            azs = await self._azs_repository.get_station(azs_external_id=azs_external_id)
            return azs

        elif terminal_external_id:
            terminal = await self._azs_repository.get_terminal(terminal_external_id=terminal_external_id)
            if terminal and terminal.azs_id:
                return terminal.azs

    async def get_company_tariff_on_transaction_time(self, company: CompanyOrm, transaction_time: datetime,
                                                     inner_group: InnerGoodsGroupOrm | None,
                                                     azs: AzsOrm | None, system_id: str) -> TariffNewOrm:
        # self.logger.info(
        #     f"{os.linesep}-> company: {company}"
        #     f"{os.linesep}-> transaction_time: {transaction_time}"
        #     f"{os.linesep}-> inner_group: {inner_group}"
        #     f"{os.linesep}-> azs: {azs}"
        #     f"{os.linesep}-> system_id: {system_id}"
        # )
        # Получаем список тарифов, действовавших для компании на момент совершения транзакции
        probable_tariffs = await self.get_probable_tariffs(
            tariff_policy_id=company.tariff_policy_id,
            system_id=system_id,
            transaction_time=transaction_time
        )

        # Перебираем тарифы и применяем первый подошедший
        for tariff in probable_tariffs:
            # АЗС
            if tariff.azs_id and azs and tariff.azs_id != azs.id:
                continue

            # Тип АЗС
            if tariff.azs_own_type and azs and tariff.azs_own_type != azs.own_type:
                continue

            # Регион
            if tariff.region_id and azs and tariff.region_id != azs.region_id:
                continue

            # Группа продуктов
            if tariff.inner_goods_group_id and inner_group and tariff.inner_goods_group_id != inner_group.id:
                continue

            # Категория продуктов
            if tariff.inner_goods_category and inner_group and \
                    tariff.inner_goods_category != inner_group.inner_category:
                continue

            # Тариф удовлетворяет критериям - возвращаем его
            return tariff

    async def get_card(self, card_id: str | None = None, card_number: str | None = None) -> CardOrm | None:
        card = await self._card_repository.get_card(card_id=card_id, card_number=card_number)
        return card

    async def process_new_remote_transaction(
            self,
            card_number: str,
            outer_goods: OuterGoodsOrm,
            azs: AzsOrm, purchase: bool,
            irrelevant_balances: IrrelevantBalances,
            comments: str,
            system_id: str,
            transaction_external_id: str | None,
            transaction_time: datetime,
            transaction_sum: float,
            transaction_fuel_volume: float,
            transaction_price: float) -> Dict[str, Any] | None:

        card = await self.get_card(card_number=card_number)
        company = await self.get_card_company_on_time(card, transaction_time)
        balance = company.overbought_balance()

        # Получаем тариф
        tariff = await self.get_company_tariff_on_transaction_time(
            company=company,
            transaction_time=transaction_time,
            inner_group=outer_goods.outer_group.inner_group if outer_goods.outer_group else None,
            azs=azs,
            system_id=system_id
        )
        if not tariff:
            self.logger.error(
                f"Не удалось определить тариф для транзакции."
                f"{os.linesep}time: {transaction_time}"
                f"{os.linesep}sum:  {transaction_sum}"
            )

        # Сумма транзакции
        transaction_type = TransactionType.PURCHASE if purchase else TransactionType.REFUND
        transaction_sum = -abs(transaction_sum) if purchase else abs(transaction_sum)

        # Сумма скидки/наценки
        discount_fee_percent = tariff.discount_fee / 100 if tariff else 0
        discount_fee_sum = banking_round(transaction_sum * discount_fee_percent)

        # Получаем итоговую сумму
        total_sum = transaction_sum + discount_fee_sum

        date_time_load = datetime.now(tz=TZ)
        transaction_data = dict(
            external_id=transaction_external_id,
            date_time=transaction_time,
            date_time_load=date_time_load,
            transaction_type=transaction_type,
            system_id=system_id,
            card_id=card.id,
            balance_id=balance.id,
            azs_code=azs.external_id,
            outer_goods_id=outer_goods.id if outer_goods else None,
            fuel_volume=-transaction_fuel_volume,
            price=transaction_price,
            transaction_sum=transaction_sum,
            tariff_new_id=tariff.id if tariff else None,
            discount_sum=discount_fee_sum if discount_fee_percent < 0 else 0,
            fee_sum=discount_fee_sum if discount_fee_percent > 0 else 0,
            total_sum=total_sum,
            company_balance_after=0,
            comments=comments,
        )

        irrelevant_balances.add_balance_irrelevancy_date_time(
            balance_id=balance.id,
            irrelevancy_date_time=date_time_load
        )
        irrelevant_balances.add_personal_account(company.personal_account)

        # Это нужно, чтобы в БД у транзакций отличалось время и можно было корректно выбрать транзакцию,
        # которая предшествовала измененной
        time.sleep(0.001)

        return transaction_data
