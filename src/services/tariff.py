from typing import List, Dict, Any

from src.database.models.tariff import TariffOrm, TariffPolicyOrm
from src.repositories.azs import AzsRepository
from src.repositories.goods import GoodsRepository
from src.repositories.system import SystemRepository
from src.repositories.tariff import TariffRepository
from src.schemas.tariff import TariffCreateSchema, TariffReadSchema, TariffEditSchema
from src.utils.exceptions import BadRequestException


class TariffService:

    def __init__(self, repository: TariffRepository) -> None:
        self.repository = repository
        self.logger = repository.logger

    async def create(self, tariff_create_schema: TariffCreateSchema) -> TariffReadSchema:
        new_tariff_obj = await self.repository.create(tariff_create_schema)
        new_tariff_data = new_tariff_obj.dumps()
        new_tariff_data['companies_amount'] = 0
        tariff_read_schema = TariffReadSchema(**new_tariff_data)
        return tariff_read_schema

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

    async def get_tariff_polices(self, with_dictionaries: bool) -> Dict[str, Any]:
        # Тарифные политики
        tariff_polices = await self.repository.get_tariff_polices()

        # Системы
        if with_dictionaries:
            system_repository = SystemRepository(session=self.repository.session, user=self.repository.user)
            systems = await system_repository.get_systems()

            # АЗС
            azs_repository = AzsRepository(session=self.repository.session, user=self.repository.user)
            stations = await azs_repository.get_stations()

            # Формируем справочник "Категория -> Продукты"
            goods_repository = GoodsRepository(session=self.repository.session, user=self.repository.user)
            categories = await goods_repository.get_categories_dictionary()

        else:
            systems = None
            stations = None
            categories = None

        data = {
            "polices": tariff_polices,
            "systems": systems,
            "azs": stations,
            "goods_categories": categories,
        }

        return data

    async def delete(self, tariff_id: str) -> None:
        await self.repository.delete_object(TariffOrm, tariff_id)
