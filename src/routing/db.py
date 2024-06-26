from typing import Any

from fastapi import APIRouter, Depends

from src.depends import get_service_db
from src.schemas.common import SuccessSchema
from src.schemas.db import DBInitSchema, DBInitialSyncSchema, DBRegularSyncSchema
from src.services.db import DBService
from src.descriptions.db import db_tag_description, db_regular_sync_description, db_initial_sync_description, \
    db_init_description
from src.utils.schemas import MessageSchema

router = APIRouter()
db_tag_metadata = {
    "name": "db",
    "description": db_tag_description,
}


@router.post(
    path="/db/init",
    tags=["db"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SuccessSchema,
    summary = 'Инициализация',
    description = db_init_description
)
async def init(
    data: DBInitSchema,
    db_service: DBService = Depends(get_service_db)
) -> dict[str, Any]:
    await db_service.init(data)
    return {'success': True}


@router.post(
    path="/db/sync/initial",
    tags=["db"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SuccessSchema,
    summary = 'Первичная синхронизация с мигрируемой БД',
    description = db_initial_sync_description
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
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = MessageSchema,
    summary = 'Регулярная синхронизация с мигрируемой БД',
    description = db_regular_sync_description
)
async def regular_sync(
    data: DBRegularSyncSchema,
    db_service: DBService = Depends(get_service_db)
) -> dict[str, Any]:
    message = await db_service.regular_sync(data)
    return {'message': message}
