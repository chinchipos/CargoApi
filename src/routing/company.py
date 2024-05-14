import uuid
from typing import List, Any

from fastapi import APIRouter, Depends

from src.database import models
from src.depends import get_service_company
from src.schemas.common import ModelIDSchema
from src.schemas.company import CompanyReadSchema, CompanyEditSchema
from src.services.company import CompanyService
from src.utils import enums
from src.utils.descriptions.company import company_tag_description, edit_company_description, get_company_description, \
    get_companies_description
from src.utils.exceptions import ForbiddenException
from src.utils.schemas import MessageSchema

router = APIRouter()
company_tag_metadata = {
    "name": "company",
    "description": company_tag_description,
}


@router.post(
    path="/company/edit",
    tags=["company"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = CompanyReadSchema,
    description = edit_company_description
)
async def edit(
    data: CompanyEditSchema,
    service: CompanyService = Depends(get_service_company)
):
    # Проверка прав доступа. Получить список систем могут только сотрудники ПроАВТО.
    major_roles = [enums.Role.CARGO_SUPER_ADMIN.name, enums.Role.CARGO_MANAGER.name]
    if service.repository.user.role.name not in major_roles:
        raise ForbiddenException()

    company = await service.edit(data)
    return company


@router.get(
    path="/company/get_company/{company_id}",
    tags=["company"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = CompanyReadSchema,
    description = get_company_description
)
async def get_company(
    company_id: uuid.UUID,
    service: CompanyService = Depends(get_service_company)
) -> Any:
    cid = str(company_id)
    minor_roles = [enums.Role.COMPANY_ADMIN.name, enums.Role.COMPANY_LOGIST.name, enums.Role.COMPANY_DRIVER.name]
    # Проверка прав доступа.
    # Суперадмин имеет права на все организации.
    # Менеджер ПроАВТО имеет права в отношении администрируемых им организаций.
    # Администратор компании, логист и водитель могут получать сведения только по своей организации,
    # при этом дминистратор компании получит расширенные сведения, а логист и водитель - ограниченные.
    # Отдать расширенные или ограниченные сведения - решение принимается при формировании сведений о компании.

    if service.repository.user.role.name == enums.Role.CARGO_MANAGER.name:
        if not service.repository.user.is_admin_for_company(cid):
            raise ForbiddenException()

    elif service.repository.user.role.name in minor_roles:
        if not service.repository.user.is_worker_of_company(cid):
            raise ForbiddenException()

    company = await service.get_company(cid)
    return company


@router.get(
    path="/company/get_companies",
    tags=["company"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[CompanyReadSchema],
    description = get_companies_description
)
async def get_companies(
    service: CompanyService = Depends(get_service_company)
) -> List[Any]:
    # Получить список организаций может любой пользователь. Состав списка зависит от роли пользователя.
    # Проверка будет выполнена при формировании списка.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    company = await service.get_companies()
    return company
