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
        self._cards_history: List[CardHistoryOrm] | None = None
        self.system_id = system_id

        self._azs_repository: AzsRepository = AzsRepository(session=session)
        self._goods_repository: GoodsRepository = GoodsRepository(session=session)
        self._card_repository: CardRepository = CardRepository(session=session)
        self._tariff_repository: TariffRepository = TariffRepository(session=session)

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

    async def get_cards_history(self, card_numbers: List[str]) -> List[CardHistoryOrm]:
        if self._cards_history is None:
            # Запрашиваем данные из БД
            self._cards_history = await self._card_repository.get_card_history(card_numbers=card_numbers)

        return self._cards_history

    def get_card_history(self, card_number: str) -> CardHistoryOrm | None:
        if self._cards_history is None:
            raise CeleryError("Список _cards_history не проиницивлизирован")

        for card_history_record in self._cards_history:
            if card_history_record.card.card_number == card_number:
                return card_history_record

    async def get_card_company(self, card: CardOrm) -> CompanyOrm:
        card_history = self.get_card_history(card.card_number)
        if card_history:
            return card_history.company

        # Если запись не найдена в истории, то возвращаем текущую организацию
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
