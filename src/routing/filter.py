from typing import List

from fastapi import APIRouter, Depends

from src.depends import get_service_tariff, get_service_filter
from src.schemas.company import CompanyReadMinimumSchema
from src.services.filter import FilterService
from src.utils import enums
from src.utils.exceptions import ForbiddenException
from src.utils.schemas import MessageSchema

router = APIRouter()
filter_tag_metadata = {
    "name": "filter",
    "description": "Получение списков сущностей с минимальным набором данных для построения пользовательских фильтров",
}


@router.get(
    path="/filter/companies",
    tags=["filter"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[CompanyReadMinimumSchema],
    summary = 'Получение списка организаций',
    description = 'Получение списка организаций'
)
async def get_companies(
    service: FilterService = Depends(get_service_filter)
):
    # Проверка прав доступа. Получить список тарифов могут только сотрудники ПроАвто
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    companies = await service.get_companies()
    return companies
