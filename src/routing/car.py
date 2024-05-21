import uuid
from typing import Any, List

from fastapi import APIRouter, Depends

from src.depends import get_service_car
from src.schemas.car import CarReadSchema, CarCreateSchema, CarEditSchema
from src.schemas.common import SuccessSchema
from src.services.car import CarService
from src.utils import enums
from src.utils.descriptions.car import delete_car_description, get_cars_description, \
    edit_car_description, create_car_description, car_tag_description
from src.utils.exceptions import ForbiddenException
from src.utils.schemas import MessageSchema

router = APIRouter()
car_tag_metadata = {
    "name": "car",
    "description": car_tag_description,
}


@router.get(
    path="/car/all",
    tags=["car"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[CarReadSchema],
    name = 'Получение списка автомобилей',
    description = get_cars_description
)
async def get_cars(
    service: CarService = Depends(get_service_car)
):
    # Получить список могут все пользователи.
    # Состав списка определяется ролью пользователя.
    # Проверка будет выполнена далее при формировании списка.
    cars = await service.get_cars()
    return cars


@router.post(
    path="/car/create",
    tags=["car"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = CarReadSchema,
    name = 'Создание записи об автомобиле',
    description = create_car_description
)
async def create(
    data: CarCreateSchema,
    service: CarService = Depends(get_service_car)
) -> CarReadSchema:
    # Проверка прав доступа будет выполнена далее
    car = await service.create(data)
    return car


@router.post(
    path="/car/{id}/edit",
    tags=["car"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = CarReadSchema,
    name = 'Редактирование автомобиля',
    description = edit_car_description
)
async def edit(
    id: uuid.UUID,
    data: CarEditSchema,
    service: CarService = Depends(get_service_car)
) -> CarReadSchema:
    _id_ = str(id)
    # Проверка прав доступа будет выполнена далее

    car = await service.edit(_id_, data)
    return car


@router.post(
    path="/car/{id}/delete",
    tags=["car"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SuccessSchema,
    name = 'Удаление автомобиля',
    description = delete_car_description
)
async def delete(
    id: uuid.UUID,
    service: CarService = Depends(get_service_car)
) -> dict[str, Any]:
    _id_ = str(id)
    # Проверка прав доступа.
    # Суперадмин ПроАВТО не имеет ограничений.
    # Менеджер ПроАВТО может удалять записи в рамках своих организаций.
    # Администратор и логист могут удалять записи только по для своей организации.
    # Водитель не имеет прав.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    await service.delete(_id_)
    return {'success': True}
