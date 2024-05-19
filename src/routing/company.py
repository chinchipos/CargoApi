import uuid
from typing import List, Any

from fastapi import APIRouter, Depends

from src.database import models
from src.depends import get_service_company
from src.schemas.company import CompanyReadSchema, CompanyEditSchema
from src.schemas.driver import DriverReadSchema
from src.services.company import CompanyService
from src.utils import enums
from src.utils.descriptions.company import company_tag_description, edit_company_description, get_company_description, \
    get_companies_description, get_company_drivers_description
from src.utils.exceptions import ForbiddenException
from src.utils.schemas import MessageSchema

router = APIRouter()
company_tag_metadata = {
    "name": "company",
    "description": company_tag_description,
}


@router.get(
    path="/company/all/",
    tags=["company"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[CompanyReadSchema],
    name = 'Получение списка всех организаций',
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


@router.get(
    path="/company/all/drivers",
    tags=["company"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[DriverReadSchema],
    name = 'Получение списка водителей всех организаций',
    description = get_company_drivers_description
)
async def get_companies_drivers(
    service: CompanyService = Depends(get_service_company)
) -> models.User:
    # Проверка прав доступа. Право есть только у суперадмина ПроАВТО
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    drivers = await service.get_drivers()
    return drivers


@router.get(
    path="/company/{company_id}/",
    tags=["company"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = CompanyReadSchema,
    name = 'Получение сведений о компании',
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


@router.post(
    path="/company/{company_id}/edit",
    tags=["company"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = CompanyReadSchema,
    name = 'Редактирование сведений об организации',
    description = edit_company_description
)
async def edit_company(
    company_id: uuid.UUID,
    data: CompanyEditSchema,
    service: CompanyService = Depends(get_service_company)
):
    cid = str(company_id)
    # Проверка прав доступа. Получить список систем могут только сотрудники ПроАВТО.
    major_roles = [enums.Role.CARGO_SUPER_ADMIN.name, enums.Role.CARGO_MANAGER.name]
    if service.repository.user.role.name not in major_roles:
        raise ForbiddenException()

    company = await service.edit(cid, data)
    return company


@router.get(
    path="/company/{company_id}/drivers",
    tags=["company"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[DriverReadSchema],
    name = 'Получение списка водителей указанной организации',
    description = get_company_drivers_description
)
async def get_company_drivers(
    company_id: uuid.UUID,
    service: CompanyService = Depends(get_service_company)
) -> models.User:
    cid = str(company_id)
    # Проверка прав доступа.
    # Суперадмин может получать любые данные.
    # Менеджер ПроАВТО может получать водителей только по своим организациям.
    # Администратор компании и логист могут получать список в рамках одной (своей) организации.
    # У водителя нет прав.
    if service.repository.user.role.name == enums.Role.CARGO_SUPER_ADMIN.name:
        pass

    elif service.repository.user.role.name == enums.Role.CARGO_MANAGER.name:
        if not service.repository.user.is_admin_for_company(cid):
            raise ForbiddenException()

    elif service.repository.user.role.name in [enums.Role.COMPANY_ADMIN.name, enums.Role.COMPANY_LOGIST.name]:
        if not service.repository.user.is_worker_of_company(cid):
            raise ForbiddenException()

    else:
        raise ForbiddenException()

    drivers = await service.get_drivers(cid)
    return drivers