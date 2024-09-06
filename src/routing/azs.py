import uuid
from typing import List, Annotated

from fastapi import APIRouter, Depends
from pydantic import Field

from src.depends import get_service_azs
from src.schemas.azs import AzsReadMinSchema
from src.services.azs import AzsService
from src.utils.enums import Role
from src.utils.exceptions import ForbiddenException
from src.utils.schemas import MessageSchema

router = APIRouter()
azs_tag_metadata = {
    "name": "azs",
    "description": "Операции с АЗС",
}


@router.get(
    path="/azs/filtered",
    tags=["azs"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[AzsReadMinSchema],
    summary = 'Получение списка АЗС по фильтру наименования',
    description = 'Получение списка АЗС по фильтру наименования'
)
async def get_filtered_stations(
    term: Annotated[str, Field(description="Строка поиска", min_length=1, max_length=10)],
    service: AzsService = Depends(get_service_azs)
):
    # Получить список карт могут все пользователи.
    # Состав списка определяется ролью пользователя. Эта проверка будет выполнена при формировании списка.
    stations = await service.get_filtered_stations(term)
    return stations


@router.get(
    path="/azs/{id}",
    tags=["azs"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = AzsReadMinSchema,
    summary = 'Получение сведений об АЗС',
    description = 'Получение сведений об АЗС'
)
async def get_station(
    id: uuid.UUID,
    service: AzsService = Depends(get_service_azs)
):
    azs_id = str(id)
    # Получить сведения могут только пользователи ПроАВТО.
    major_roles = [Role.CARGO_SUPER_ADMIN.name, Role.CARGO_MANAGER.name]
    if service.repository.user.role.name not in major_roles:
        raise ForbiddenException()

    station = await service.get_station(azs_id=azs_id)
    return station
