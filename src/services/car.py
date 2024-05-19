from typing import List

from src.database import models
from src.repositories.car import CarRepository
from src.schemas.common import ModelIDSchema
from src.schemas.car import CarCreateSchema, CarReadSchema, CarEditSchema
from src.utils import enums
from src.utils.exceptions import BadRequestException, ForbiddenException


class CarService:

    def __init__(self, repository: CarRepository) -> None:
        self.repository = repository
        self.logger = repository.logger

    async def create(self, car_create_schema: CarCreateSchema) -> CarReadSchema:
        # Проверка прав доступа.
        # Суперадмин ПроАВТО не имеет ограничений.
        # Менеджер ПроАВТО может создавать записи в рамках своих организаций.
        # Администратор и логист могут создавать записи только по для своей организации.
        # Водитель не имеет прав.
        company_id = car_create_schema.company_id
        if self.repository.user.role.name == enums.Role.CARGO_SUPER_ADMIN.name:
            pass

        elif self.repository.user.role.name == enums.Role.CARGO_MANAGER.name:
            if not self.repository.user.is_admin_for_company(company_id):
                raise ForbiddenException()

        elif self.repository.user.role.name in [enums.Role.COMPANY_ADMIN.name, enums.Role.COMPANY_LOGIST.name]:
            if not self.repository.user.is_worker_of_company(company_id):
                raise ForbiddenException()

        else:
            raise ForbiddenException()

        # Создаем объект
        car_read_schema = await self.repository.create(car_create_schema)
        return car_read_schema

    async def edit(self, car_id: str, car_edit_schema: CarEditSchema) -> CarReadSchema:
        # Получаем объект из БД
        car_obj = await self.repository.get_car(car_id)
        if not car_obj:
            raise BadRequestException('Запись не найдена')

        # Получаем информацию о том к какой компании относится автомобиль
        company_id = car_obj.company_id

        # Проверка прав доступа.
        # Суперадмин ПроАВТО не имеет ограничений.
        # Менеджер ПроАВТО может редактировать записи в рамках своих организаций.
        # Администратор и логист могут редактировать записи только по для своей организации.
        # Водитель не имеет прав.
        if self.repository.user.role.name == enums.Role.CARGO_SUPER_ADMIN.name:
            pass

        elif self.repository.user.role.name == enums.Role.CARGO_MANAGER.name:
            if not self.repository.user.is_admin_for_company(company_id):
                raise ForbiddenException()

        elif self.repository.user.role.name in [enums.Role.COMPANY_ADMIN.name, enums.Role.COMPANY_LOGIST.name]:
            if not self.repository.user.is_worker_of_company(company_id):
                raise ForbiddenException()

        else:
            raise ForbiddenException()

        # Обновляем данные, сохраняем в БД
        car_read_schema = await self.repository.edit(car_edit_schema)


        update_data = car_edit_schema.model_dump(exclude_unset=True)
        await self.repository.update_model_instance(car_obj, update_data)

        # Формируем ответ
        # car_read_schema = CarReadSchema.model_validate(car_obj)
        car_data = car_obj.dumps()
        car_data['drivers'] = [cd.driver for cd in car_obj.car_driver]
        car_read_schema = CarReadSchema(**car_data)
        return car_read_schema

    async def get_cars(self) -> List[models.Car]:
        cars = await self.repository.get_cars()
        return cars

    async def delete(self, car_id: str) -> None:
        # Получаем объект из БД
        car_obj = await self.repository.get_car(car_id)
        if not car_obj:
            raise BadRequestException('Запись не найдена')

        # Получаем информацию о том к какой компании относится автомобиль
        company_id = car_obj.company_id

        # Проверка прав доступа.
        # Суперадмин ПроАВТО не имеет ограничений.
        # Менеджер ПроАВТО может редактировать записи в рамках своих организаций.
        # Администратор и логист могут редактировать записи только по для своей организации.
        # Водитель не имеет прав.
        if self.repository.user.role.name == enums.Role.CARGO_SUPER_ADMIN.name:
            pass

        elif self.repository.user.role.name == enums.Role.CARGO_MANAGER.name:
            if not self.repository.user.is_admin_for_company(company_id):
                raise ForbiddenException()

        elif self.repository.user.role.name in [enums.Role.COMPANY_ADMIN.name, enums.Role.COMPANY_LOGIST.name]:
            if not self.repository.user.is_worker_of_company(company_id):
                raise ForbiddenException()

        else:
            raise ForbiddenException()

        await self.repository.delete_one(models.Car, car_id)
