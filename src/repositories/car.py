from typing import List, Optional

from sqlalchemy import select as sa_select
from sqlalchemy.orm import joinedload

from src.database.models.company import CompanyOrm
from src.database.models.user import UserOrm
from src.database.models.car import CarOrm, CarDriverOrm
from src.repositories.base import BaseRepository
from src.schemas.car import CarCreateSchema, CarReadSchema, CarEditSchema
from src.utils import enums
from src.utils.exceptions import BadRequestException


class CarRepository(BaseRepository):

    async def create(self, create_schema: CarCreateSchema) -> CarReadSchema:
        # Выполняем проверку водителей
        drivers = []
        if create_schema.driver_ids:
            # Получаем список водителей.
            stmt = (
                sa_select(UserOrm)
                .options(
                    joinedload(UserOrm.role)
                )
                .where(UserOrm.id.in_(create_schema.driver_ids))
                .distinct()
            )
            drivers = await self.select_all(stmt)
            # Проверяем что все водители имеют соответствующую роль
            for driver in drivers:
                if driver.role.name != enums.Role.COMPANY_DRIVER.name:
                    raise BadRequestException('Водитель не обладает соответствующей ролью, либо не найден')

            # Проверяем, что водители, принадлежат к той же организации, что и создаваемый автомобиль
            for driver in drivers:
                if driver.company_id != create_schema.company_id:
                    raise BadRequestException('Автомобиль и водитель не могут принадлежать к разным организациям')

        # Создаем автомобиль
        initial_data = create_schema.model_dump(exclude_unset=True)
        initial_data.pop('driver_ids', None)
        new_car = CarOrm(**initial_data)
        await self.save_object(new_car)

        # Привязываем водителей к автомобилю
        for driver in drivers:
            await self.insert_or_update(
                CarDriverOrm,
                index_field = 'id',
                car_id = new_car.id,
                driver_id = driver.id
            )

        # Получаем из БД запись о созданном автомобиле
        new_car_obj = await self.get_car(new_car.id)
        # car_read_schema = CarReadSchema.model_validate(new_car_obj)
        car_data = new_car_obj.dumps()
        car_data['drivers'] = [cd.driver for cd in new_car_obj.car_driver]
        car_read_schema = CarReadSchema(**car_data)

        return car_read_schema

    async def edit(self, edit_schema: CarEditSchema) -> CarReadSchema:
        # Выполняем проверку водителей
        drivers = []
        if edit_schema.driver_ids:
            # Получаем список водителей.
            stmt = (
                sa_select(UserOrm)
                .options(
                    joinedload(UserOrm.role)
                )
                .where(UserOrm.id.in_(edit_schema.driver_ids))
                .distinct()
            )
            drivers = await self.select_all(stmt)
            # Проверяем что все водители имеют соответствующую роль
            for driver in drivers:
                if driver.role.name != enums.Role.COMPANY_DRIVER.name:
                    raise BadRequestException('Водитель не обладает соответствующей ролью, либо не найден')

            # Проверяем, что водители, принадлежат к той же организации, что и создаваемый автомобиль
            for driver in drivers:
                if driver.company_id != edit_schema.company_id:
                    raise BadRequestException('Автомобиль и водитель не могут принадлежать к разным организациям')

        # Создаем автомобиль
        initial_data = edit_schema.model_dump(exclude_unset=True)
        initial_data.pop('driver_ids', None)
        new_car = CarOrm(**initial_data)
        await self.save_object(new_car)

        # Привязываем водителей к автомобилю
        for driver in drivers:
            await self.insert_or_update(
                CarDriverOrm,
                index_field = 'id',
                car_id = new_car.id,
                driver_id = driver.id
            )

        # Получаем из БД запись о созданном автомобиле
        new_car_obj = await self.get_car(new_car.id)
        # car_read_schema = CarReadSchema.model_validate(new_car_obj)
        car_data = new_car_obj.dumps()
        car_data['drivers'] = [cd.driver for cd in new_car_obj.car_driver]
        car_read_schema = CarReadSchema(**car_data)

        return car_read_schema

    async def get_car(self, car_id: str) -> Optional[CarOrm]:
        stmt = (
            sa_select(CarOrm)
            .options(
                joinedload(CarOrm.car_driver).joinedload(CarDriverOrm.driver),
                joinedload(CarOrm.company)
            )
            .where(CarOrm.id == car_id)
        )
        car = await self.select_first(stmt)
        return car

    async def get_cars(self) -> List[CarOrm]:
        stmt = (
            sa_select(CarOrm)
            .options(
                joinedload(CarOrm.car_driver).joinedload(CarDriverOrm.driver),
                joinedload(CarOrm.company)
            )
            .join(CarOrm.company)
            .order_by(CompanyOrm.name, CarOrm.model)
        )

        if self.user.role.name == enums.Role.CARGO_MANAGER.name:
            stmt = stmt.where(CarOrm.company_id.in_(self.user.company_ids_subquery()))

        elif self.user.role.name in [enums.Role.COMPANY_ADMIN.name, enums.Role.COMPANY_LOGIST.name]:
            stmt = stmt.where(CarOrm.company_id == self.user.company_id)

        elif self.user.role.name == enums.Role.COMPANY_DRIVER.name:
            stmt = (
                stmt
                .join(CarOrm.car_driver)
                .where(CarOrm.company_id == self.user.company_id)
                .where(CarDriverOrm.driver_id == self.user.id)
            )

        cars = await self.select_all(stmt)
        return cars
