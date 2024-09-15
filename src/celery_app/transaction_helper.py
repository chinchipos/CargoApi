import copy
from datetime import datetime
from logging import Logger
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from src.celery_app.exceptions import CeleryError
from src.database.models import CardOrm, CompanyOrm, InnerGoodsGroupOrm, AzsOrm, TariffNewOrm, CardHistoryOrm, \
    OuterGoodsOrm
from src.repositories.azs import AzsRepository
from src.repositories.base import BaseRepository
from src.repositories.card import CardRepository
from src.repositories.goods import GoodsRepository
from src.repositories.tariff import TariffRepository


class TransactionHelper(BaseRepository):

    def __init__(self, session: AsyncSession, logger: Logger, system_id: str = None):
        super().__init__(session, None)
        self.logger = logger
        self._tariffs: List[TariffNewOrm] | None = None
        self._card_history: List[CardHistoryOrm] | None = None
        self.system_id = system_id

        self._azs_repository: AzsRepository | None = None
        self._goods_repository: GoodsRepository | None = None

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

    async def get_tariffs(self, system_id: str) -> List[TariffNewOrm]:
        if self._tariffs is None:
            self.logger.info("Запрашиваю из БД тарифы")
            tariff_repository = TariffRepository(session=self.session)
            self._tariffs = copy.deepcopy(await tariff_repository.get_tariffs())

        tariffs = [tariff for tariff in self._tariffs if tariff.system_id == system_id]
        return tariffs

    async def get_card_history(self) -> List[CardHistoryOrm]:
        if self._card_history is None:
            self.logger.info("Запрашиваю из БД историю владения картами")
            card_repository = CardRepository(session=self.session)
            self._card_history = await card_repository.get_card_history()

        return self._card_history

    async def get_card_company(self, card: CardOrm) -> CompanyOrm:
        for card_history_record in await self.get_card_history():
            if card_history_record.card_id == card.id:
                return card_history_record.company

        # Если запись не найдена в истории, то возвращаем текущую организацию
        if card.company_id and card.company:
            return card.company

        raise CeleryError(f"Не удалось определить организацию для карты {card.card_number}")

    async def get_outer_goods_item(self, goods_external_id: str) -> OuterGoodsOrm | None:
        self.logger.info("Запрашиваю продукт из БД")
        if not self._goods_repository:
            self._goods_repository = GoodsRepository(session=self.session)

        outer_goods = await self._goods_repository.get_outer_goods_item(outer_goods_external_id=goods_external_id)
        return outer_goods

    async def get_azs(self, azs_external_id: str = None, terminal_external_id: str = None) -> AzsOrm:
        self.logger.info("Запрашиваю АЗС из БД")
        if not self._azs_repository:
            self._azs_repository = AzsRepository(session=self.session)

        if azs_external_id:
            azs = await self._azs_repository.get_station(azs_external_id=azs_external_id)
            return azs

        elif terminal_external_id:
            terminal = await self._azs_repository.get_terminal(terminal_external_id=terminal_external_id)
            if terminal and terminal.azs_id:
                return terminal.azs

    async def get_company_tariff_on_transaction_time(self, company: CompanyOrm, transaction_time: datetime,
                                                     inner_group: InnerGoodsGroupOrm | None,
                                                     azs: AzsOrm | None, system_id: str = None) -> TariffNewOrm:

        # Получаем список тарифов, действовавших для компании на момент совершения транзакции
        tariffs = []
        system_tariffs = await self.get_tariffs(system_id)
        for tariff in system_tariffs:
            if tariff.policy_id == company.tariff_policy_id and tariff.begin_time <= transaction_time:
                if (tariff.end_time and tariff.begin_time <= transaction_time < tariff.end_time) \
                        or not tariff.end_time:
                    tariffs.append(tariff)

        # Перебираем тарифы и применяем первый подошедший
        for tariff in tariffs:
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
