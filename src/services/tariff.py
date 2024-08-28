import copy
from datetime import datetime
from typing import List, Dict, Any

from src.config import TZ
from src.database.models.tariff import TariffOrm, TariffNewOrm
from src.repositories.azs import AzsRepository
from src.repositories.goods import GoodsRepository
from src.repositories.system import SystemRepository
from src.repositories.tariff import TariffRepository
from src.schemas.tariff import TariffReadSchema, TariffEditSchema, TariffNewCreateSchema
from src.utils.exceptions import BadRequestException


class TariffService:

    def __init__(self, repository: TariffRepository) -> None:
        self.repository = repository
        self.logger = repository.logger
        self.now = datetime.now(tz=TZ)

    async def save(self, tariff_create_schema: TariffNewCreateSchema) -> None:
        if tariff_create_schema.policy_id:
            policy_id = tariff_create_schema.policy_id
        else:
            # Создаем новую тарифную политику
            policy_name = tariff_create_schema.policy_name.strip()
            if not policy_name:
                raise BadRequestException("Не указано наименование тарифа")

            try:
                policy = await self.repository.create_tariff_policy(policy_name=policy_name)
                policy_id = policy.id
            except Exception:
                raise BadRequestException("Тариф с аналогичным наименованием уже существует.")

        # Получаем политику вместе с ее тарифами
        policy = await self.repository.get_tariff_policy(policy_id=policy_id)

        # Сравниваем по параметрам полученные тарифы с существующими
        # Если полученный тариф отсутствует в БД, то сохраняем его.
        # Если найден в БД, то, при наличиии изменений, архивируем действующий, создаем новый
        for received_tariff in tariff_create_schema.tariffs:
            found = False
            need_update = False
            for saved_tariff in policy.tariffs:
                if received_tariff.system_id == saved_tariff.system_id and \
                        received_tariff.azs_own_type == saved_tariff.azs_own_type and \
                        received_tariff.region_id == saved_tariff.region_id and \
                        received_tariff.goods_group_id == saved_tariff.inner_goods_group_id and \
                        received_tariff.goods_category == saved_tariff.inner_goods_category:

                    found = True
                    if received_tariff.discount_fee != saved_tariff.discount_fee:
                        need_update = True
                        # Архивируем действующий тариф
                        saved_tariff.end_time = self.now
                        await self.repository.save_object(saved_tariff)

            # Создаем новый тариф
            begin_time = datetime(year=2020, month=1, day=1) if not found else self.now
            if not found or need_update:
                await self.repository.create_tariff(
                    policy_id=policy_id,
                    system_id=received_tariff.system_id,
                    azs_own_type=received_tariff.azs_own_type,
                    region_id=received_tariff.region_id,
                    goods_group_id=received_tariff.goods_group_id,
                    goods_category=received_tariff.goods_category,
                    discount_fee=received_tariff.discount_fee,
                    begin_time=begin_time
                )

    async def edit(self, tariff_id: str, tariff_edit_schema: TariffEditSchema) -> TariffReadSchema:
        # Получаем тариф из БД
        tariff_obj = await self.repository.session.get(TariffOrm, tariff_id)
        if not tariff_obj:
            raise BadRequestException('Запись не найдена')

        # Обновляем данные, сохраняем в БД
        update_data = tariff_edit_schema.model_dump(exclude_unset=True)
        await self.repository.update_object(tariff_obj, update_data)

        # Формируем ответ
        # companies_amount = await self.repository.get_companies_amount(tariff_id)
        # tariff_obj.annotate({'companies_amount': companies_amount})
        tariff_read_schema = TariffReadSchema.model_validate(tariff_obj)
        return tariff_read_schema

    async def get_tariffs(self) -> List[TariffOrm]:
        tariffs = await self.repository.get_tariffs()
        return tariffs

    async def get_tariff_polices(self, with_dictionaries: bool, filters: Dict[str, str]) -> Dict[str, Any]:
        # Тарифные политики
        tariff_polices = await self.repository.get_tariff_polices(filters=filters)
        tariff_polices = copy.deepcopy(tariff_polices)

        dictionaries = None
        if with_dictionaries:
            # Тарифные политики
            polices = await self.repository.get_tariff_polices_without_tariffs()

            # Системы
            system_repository = SystemRepository(session=self.repository.session, user=self.repository.user)
            systems = await system_repository.get_systems()

            # Типы АЗС
            azs_repository = AzsRepository(session=self.repository.session, user=self.repository.user)
            azs_own_types = await azs_repository.get_azs_own_types_dictionary()

            # Список АЗС
            # azs_stations = await azs_repository.get_stations()

            # Регионы
            regions = await self.repository.get_regions()

            # Формируем справочник "Категория -> Продукты"
            goods_repository = GoodsRepository(session=self.repository.session, user=self.repository.user)
            categories = await goods_repository.get_categories_dictionary()

            dictionaries = {
                "polices": polices,
                "systems": systems,
                # "azs_stations": azs_stations,
                "regions": regions,
                "azs_own_types": azs_own_types,
                "goods_categories": categories,
            }

        data = {
            "polices": tariff_polices,
            "dictionaries": dictionaries
        }

        return data

    async def delete(self, tariff_id: str) -> None:
        # Получаем запись из БД
        tariff: TariffNewOrm = await self.repository.session.get(TariffNewOrm, tariff_id)
        tariff.end_time = self.now
        await self.repository.save_object(tariff)
