import os
from datetime import datetime

from lxml import etree
from sqlalchemy.ext.asyncio import AsyncSession
from zeep.exceptions import Fault

from src.celery_app.exceptions import CeleryError
from src.celery_app.ops.api import OpsApi
from src.database.models import CardOrm, SystemOrm, CardSystemOrm
from src.database.models.card import BlockingCardReason
from src.repositories.base import BaseRepository
from src.repositories.card import CardRepository
from src.repositories.card_type import CardTypeRepository
from src.repositories.system import SystemRepository
from src.utils.enums import ContractScheme, System
from src.utils.loggers import get_logger


class OpsController(BaseRepository):

    def __init__(self, session: AsyncSession):
        super().__init__(session, None)
        self.logger = get_logger(name="GPNController", filename="celery.log")
        self.api = OpsApi()

        self.system = None

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

    async def import_new_cards(self) -> None:
        self.api.show_wsdl_methods("Cards")
        self.logger.info("Начинаю импорт карт")
        try:
            start_time = datetime.now()

            # Получаем все карты из ОПС
            remote_cards = self.api.get_remote_cards()

            for card in remote_cards:
                if card["cardStateID"] in [4, 6, "4", "6"]:
                    print(card)

            # Получаем все карты из БД
            card_repository = CardRepository(session=self.session, user=None)
            local_cards = await card_repository.get_cards_by_filters(system_id=self.system.id)

            # Сравниваем списки. Одинаковые записи исключаем из обоих списков для уменьшения стоимости алгоритма.
            i = 0
            while i < len(remote_cards):
                remote_card = remote_cards[i]
                found = False
                for local_card in local_cards:
                    if local_card.card_number == str(remote_card["cardNumber"]):
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
                    "card_number": str(remote_card["cardNumber"]),
                    "card_type_id": plastic_card_type.id,
                    "is_active": True if remote_card["cardStateID"] == 0 else False,
                } for remote_card in remote_cards
            ]
            await self.bulk_insert_or_update(CardOrm, new_cards_dataset, "card_number")

            # Получаем вновь созданные карты из БД.
            new_cards = await card_repository.get_cards_by_filters(
                card_numbers=[card["card_number"] for card in new_cards_dataset]
            )
            # new_cards = await card_repository.get_cards_by_filters(
            #     card_numbers=[str(remote_card["cardNumber"]) for remote_card in remote_cards]
            # )

            # Привязываем карты к системе
            card_system_dataset = [
                {
                    "card_id": card.id,
                    "system_id": self.system.id
                } for card in new_cards
            ]
            await self.bulk_insert_or_update(CardSystemOrm, card_system_dataset)

            # Получаем вновь созданные карты из БД с заблокированным статусом
            blocked_remote_cards = [remote_card for remote_card in remote_cards if remote_card["cardStateID"] in [4, 6, "4", "6"]]
            if blocked_remote_cards:
                new_cards = await card_repository.get_cards_by_filters(
                    card_numbers=[str(remote_card["cardNumber"]) for remote_card in blocked_remote_cards]
                )

                # Записываем причину блокировки карты, если таковая имела место
                for new_card in new_cards:
                    for remote_card in blocked_remote_cards:
                        if new_card.card_number == str(remote_card["cardNumber"]):
                            if remote_card["cardStateID"] == 4:
                                new_card.reason_for_blocking = BlockingCardReason.COMPANY
                            elif remote_card["cardStateID"] == 6:
                                new_card.reason_for_blocking = BlockingCardReason.PIN
                            await self.save_object(new_card)
                            blocked_remote_cards.remove(remote_card)
                            break

            end_time = datetime.now()
            self.logger.info(f'Импорт карт завершен. Время выполнения: {str(end_time - start_time).split(".")[0]}. '
                             f'Количество новых карт: {len(new_cards_dataset)}')

        except Fault as e:
            text = f"---------------------{os.linesep}"
            text += f"{e.message}{os.linesep}"

            hist = self.api.history.last_sent
            text += f"---------------------{os.linesep}"
            text += f"{etree.tostring(hist["envelope"], encoding="unicode", pretty_print=True)}"

            # Строка закомментирована, так как ответ сервера может оказаться очень длинным.
            # Раскомментировать при необходимости.
            # hist = self.api.history.last_received
            # text += f"---------------------{os.linesep}"
            # text += f"{etree.tostring(hist["envelope"], encoding="unicode", pretty_print=True)}"
