from typing import List, Annotated

from fastapi import APIRouter, Depends
from pydantic import Field

from src.depends import get_service_azs
from src.schemas.azs import AzsReadMinSchema
from src.services.azs import AzsService
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
