from typing import Any

from fastapi import APIRouter, Depends

from src.depends import get_service_db, get_service_db_init
from src.schemas.common import SuccessSchema
from src.schemas.db import DBInitSchema, DBInitialSyncSchema, DBRegularSyncSchema
from src.services.db import DBService
from src.utils.schemas import Message

router = APIRouter()
db_tag_metadata = {
    "name": "db",
    "description": "Сервисные операции с базой данных.",
}


@router.post(
    path="/db/init",
    tags=["db"],
    responses = {400: {'model': Message, "description": "Bad request"}},
    response_model = SuccessSchema,
    description = (
        """
        **Инициализация БД.**<br>
        <br>
        1. Создание справочника ролей.<br>
        2. Создание первого суперадмина.<br>
        3. Создание справочника типов карт.<br>
        <br>
        **Входные параметры (передаются в теле запроса):**<br>
        <br>
        **service_token** - сервисный токен, указанный в главном конфигурационном 
        файле (**.env**).<br>
        **superuser_password** - пароль для первого суперадмина (логин - **cargo**).
        """
    )
)
async def init(
    data: DBInitSchema,
    db_service: DBService = Depends(get_service_db_init)
) -> dict[str, Any]:
    await db_service.init(data)
    return {'success': True}


@router.post(
    path="/db/sync/initial",
    tags=["db"],
    responses = {400: {'model': Message, "description": "Bad request"}},
    response_model = SuccessSchema,
    description = (
        """
        Коннектор для первичной синхронизации локальной БД с БД основной площадки. Прогружаются следующие данные.<br>
        <br>
        1. Системы.<br>
        2. Тарифы.<br>
        3. Организации.<br>
        4. Автомобили.<br>
        5. Топливные карты.<br>
        6. Товары / услуги.<br>
        7. Транзакции.<br>
        <br>
        **Входные параметры (передаются в теле запроса):**<br>
        <br>
        **service_token** - сервисный токен, указанный в главном конфигурационном 
        файле (**.env**).
        """
    )
)
async def initial_sync(
    data: DBInitialSyncSchema,
    db_service: DBService = Depends(get_service_db)
) -> dict[str, Any]:
    await db_service.initial_sync(data)
    return {'success': True}


@router.post(
    path="/db/sync/regular",
    tags=["db"],
    responses = {400: {'model': Message, "description": "Bad request"}},
    response_model = SuccessSchema,
    description = (
        """
        Коннектор для регулярной синхронизации локальной БД с БД основной площадки. Прогружаются следующие данные:<br>
        <br>
        1. Организации.<br>
        <br>
        **Входные параметры (передаются в теле запроса):**<br>
        <br>
        **service_token** - сервисный токен, указанный в главном конфигурационном 
        файле (**.env**).
        """
    )
)
async def regular_sync(
    data: DBRegularSyncSchema,
    db_service: DBService = Depends(get_service_db)
) -> dict[str, Any]:
    await db_service.regular_sync(data)
    return {'success': True}
