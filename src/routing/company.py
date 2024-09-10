import uuid
from typing import List, Any

from fastapi import APIRouter, Depends

from src.depends import get_service_company
from src.descriptions.company import company_tag_description, edit_company_description, get_company_description, \
    get_companies_description, get_company_drivers_description, bind_manager_to_company_description, \
    edit_balance_description, create_company_description, get_notifications_description
from src.schemas.common import SuccessSchema
from src.schemas.company import CompanyReadSchema, CompanyEditSchema, CompanyBalanceEditSchema, CompanyCreateSchema, \
    CompaniesReadSchema
from src.schemas.driver import DriverReadSchema
from src.schemas.notification import NotifcationMailingReadSchema
from src.services.company import CompanyService
from src.utils import enums
from src.utils.exceptions import ForbiddenException, BadRequestException
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
    response_model = CompaniesReadSchema,
    summary = 'Получение списка всех организаций',
    description = get_companies_description
)
async def get_companies(
    with_dictionaries: bool = False,
    tariff_policy_id: str = None,
    service: CompanyService = Depends(get_service_company)
):
    # Получить список организаций может любой пользователь. Состав списка зависит от роли пользователя.
    # Проверка будет выполнена при формировании списка.
    filters = {
        "tariff_policy_id": tariff_policy_id,
    }
    companies = await service.get_companies(with_dictionaries=with_dictionaries, filters=filters)
    return companies


@router.get(
    path="/company/notifications",
    tags=["company"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[NotifcationMailingReadSchema],
    summary = 'Получение списка уведомлений для организации',
    description = get_notifications_description
)
async def get_notifications(
    service: CompanyService = Depends(get_service_company)
):
    # Получить список уведомлений может только администратор организации
    if service.repository.user.role.name != enums.Role.COMPANY_ADMIN.name:
        raise ForbiddenException()

    notifications = await service.get_notifications()
    return notifications


@router.get(
    path="/company/notifications/{mailing_id}/read",
    tags=["company"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SuccessSchema,
    summary = 'Уведомление прочитано',
    description = 'Уведомление прочитано'
)
async def notification_read(
    mailing_id: str,
    service: CompanyService = Depends(get_service_company)
):
    # Прочитать уведомление может только администратор организации
    if service.repository.user.role.name != enums.Role.COMPANY_ADMIN.name:
        raise ForbiddenException()

    await service.notification_read(mailing_id)
    return {'success': True}


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
    # Проверка прав доступа. Создавать организации может только суперадмин.
    if service.repository.user.role.name != enums.Role.CARGO_SUPER_ADMIN.name:
        raise ForbiddenException()

    # Проверяем входные данные
    if data.overdraft_on:
        # Если активирован овердрафт, то обязательно должны быть заполнены поля: сумма, дни
        if data.overdraft_sum is None:
            raise BadRequestException("Не указана сумма овердрафта")

        if not data.overdraft_days:
            raise BadRequestException("Не указан срок овердрафта")

        if not data.overdraft_fee_percent:
            raise BadRequestException("Не указан размер комиссии за овердрафт")

    system = await service.create(data)
    return system


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
):
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
