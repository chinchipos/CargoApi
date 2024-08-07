import uuid
from typing import List, Any

from fastapi import APIRouter, Depends

from src.database.model import models
from src.depends import get_service_company
from src.descriptions.company import company_tag_description, edit_company_description, get_company_description, \
    get_companies_description, get_company_drivers_description, bind_manager_to_company_description, \
    edit_balance_description, create_company_description
from src.schemas.common import SuccessSchema
from src.schemas.company import CompanyReadSchema, CompanyEditSchema, CompanyBalanceEditSchema, CompanyCreateSchema
from src.schemas.driver import DriverReadSchema
from src.services.company import CompanyService
from src.utils import enums
from src.utils.exceptions import ForbiddenException
from src.utils.schemas import MessageSchema

router = APIRouter()
company_tag_metadata = {
    "name": "company",
    "description": company_tag_description,
}


@router.get(
    path="/company/all",
    tags=["company"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[CompanyReadSchema],
    summary = 'Получение списка всех организаций',
    description = get_companies_description
)
async def get_companies(
    service: CompanyService = Depends(get_service_company)
):
    # Получить список организаций может любой пользователь.
    # Состав списка зависит от роли пользователя.
    # Проверка будет выполнена при формировании списка.

    companies = await service.get_companies()
    return companies

"""
@router.get(
    path="/company/all/drivers",
    tags=["company"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[DriverReadSchema],
    summary = 'Получение списка водителей всех организаций',
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
"""


@router.get(
    path="/company/{id}",
    tags=["company"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = CompanyReadSchema,
    summary = 'Получение сведений о компании',
    description = get_company_description
)
async def get_company(
    id: uuid.UUID,
    service: CompanyService = Depends(get_service_company)
):
    id = str(id)
    minor_roles = [enums.Role.COMPANY_ADMIN.name, enums.Role.COMPANY_LOGIST.name, enums.Role.COMPANY_DRIVER.name]
    # Проверка прав доступа.
    # Суперадмин имеет права на все организации.
    # Менеджер ПроАВТО имеет права в отношении администрируемых им организаций.
    # Администратор компании, логист и водитель могут получать сведения только по своей организации,
    # при этом дминистратор компании получит расширенные сведения, а логист и водитель - ограниченные.
    # Отдать расширенные или ограниченные сведения - решение принимается при формировании сведений о компании.

    if service.repository.user.role.name == enums.Role.CARGO_MANAGER.name:
        if not service.repository.user.is_admin_for_company(id):
            raise ForbiddenException()

    elif service.repository.user.role.name in minor_roles:
        if not service.repository.user.is_worker_of_company(id):
            raise ForbiddenException()

    company = await service.get_company(id)
    return company


@router.post(
    path="/company/create",
    tags=["company"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = CompanyReadSchema,
    summary = 'Создание организации',
    description = create_company_description
)
async def create(
    data: CompanyCreateSchema,
    service: CompanyService = Depends(get_service_company)
):
    # Проверка прав доступа. Создавать системы может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    system = await service.create(data)
    return system


@router.put(
    path="/company/{id}/edit",
    tags=["company"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = CompanyReadSchema,
    summary = 'Редактирование сведений об организации',
    description = edit_company_description
)
async def edit_company(
    id: uuid.UUID,
    data: CompanyEditSchema,
    service: CompanyService = Depends(get_service_company)
):
    id = str(id)
    company = await service.edit(id, data)
    return company


@router.put(
    path="/company/{id}/balance/edit",
    tags=["company"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SuccessSchema,
    summary = 'Редактирование баланса организации',
    description = edit_balance_description
)
async def edit_balance(
    id: uuid.UUID,
    data: CompanyBalanceEditSchema,
    service: CompanyService = Depends(get_service_company)
):
    id = str(id)
    await service.edit_company_balance(id, data)
    return {'success': True}


@router.get(
    path="/company/{id}/bind/manager/{user_id}",
    tags=["company"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SuccessSchema,
    summary = 'Привязка менеджера к компании',
    description = bind_manager_to_company_description
)
async def bind_manager(
    id: uuid.UUID,
    user_id: uuid.UUID,
    service: CompanyService = Depends(get_service_company)
) -> dict[str, Any]:
    id = str(id)
    user_id = str(user_id)

    # Выполнять операцию имеет право только суперадмин ПроАВТО.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    await service.bind_manager(id, user_id)
    return {'success': True}


@router.get(
    path="/company/{id}/drivers",
    tags=["company"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[DriverReadSchema],
    summary = 'Получение списка водителей указанной организации',
    description = get_company_drivers_description
)
async def get_company_drivers(
    id: uuid.UUID,
    service: CompanyService = Depends(get_service_company)
) -> models.User:
    id = str(id)
    # Проверка прав доступа.
    # Суперадмин может получать любые данные.
    # Менеджер ПроАВТО может получать водителей только по своим организациям.
    # Администратор компании и логист могут получать список в рамках одной (своей) организации.
    # У водителя нет прав.
    if service.repository.user.role.name == enums.Role.CARGO_SUPER_ADMIN.name:
        pass

    elif service.repository.user.role.name == enums.Role.CARGO_MANAGER.name:
        if not service.repository.user.is_admin_for_company(id):
            raise ForbiddenException()

    elif service.repository.user.role.name in [enums.Role.COMPANY_ADMIN.name, enums.Role.COMPANY_LOGIST.name]:
        if not service.repository.user.is_worker_of_company(id):
            raise ForbiddenException()

    else:
        raise ForbiddenException()

    drivers = await service.get_drivers(id)
    return drivers
