import copy
from datetime import datetime
from typing import List, Dict, Any

from src.config import TZ
from src.database.models.tariff import TariffOrm
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
                if received_tariff.azs_id == saved_tariff.azs_id and \
                        received_tariff.goods_group_id == saved_tariff.inner_goods_group_id and \
                        received_tariff.goods_category == saved_tariff.inner_goods_category:

                    found = True
                    if received_tariff.discount_fee != saved_tariff.discount_fee or \
                            received_tariff.discount_fee_franchisee != saved_tariff.discount_fee_franchisee:
                        need_update = True
                        # Архивируем действующий тариф
                        saved_tariff.end_time = self.now
                        await self.repository.save_object(saved_tariff)

            # Создаем новый тариф
            if not found or need_update:
                await self.repository.create_tariff(
                    policy_id=policy_id,
                    system_id=received_tariff.system_id,
                    azs_id=received_tariff.azs_id,
                    goods_group_id=received_tariff.goods_group_id,
                    goods_category=received_tariff.goods_category,
                    discount_fee=received_tariff.discount_fee,
                    discount_fee_franchisee=received_tariff.discount_fee_franchisee
                )

        print('333333333333333333333333333333333333333333')
        print(received_tariff)

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
        # Системы
        if with_dictionaries:
            polices = await self.repository.get_tariff_polices_without_tariffs()
            system_repository = SystemRepository(session=self.repository.session, user=self.repository.user)
            systems = await system_repository.get_systems()

            # АЗС
            azs_repository = AzsRepository(session=self.repository.session, user=self.repository.user)
            stations = await azs_repository.get_stations()

            # Формируем справочник "Категория -> Продукты"
            goods_repository = GoodsRepository(session=self.repository.session, user=self.repository.user)
            categories = await goods_repository.get_categories_dictionary()

        else:
            polices = None
            systems = None
            stations = None
            categories = None

        data = {
            "polices": tariff_polices,
            "dictionaries": {
                "polices": polices,
                "systems": systems,
                "azs": stations,
                "goods_categories": categories,
            }
        }

        return data

    async def delete(self, tariff_id: str) -> None:
        await self.repository.delete_object(TariffOrm, tariff_id)
