from typing import Any

from fastapi import APIRouter, Depends

from src.depends import get_service_db
from src.routing.descriptions import db_initial_sync_descr, db_regular_sync_descr, db_init_descr
from src.schemas.common import SuccessSchema
from src.schemas.db import DBInitSchema, DBInitialSyncSchema, DBRegularSyncSchema
from src.services.db import DBService
from src.utils.schemas import MessageSchema

router = APIRouter()
db_tag_metadata = {
    "name": "db",
    "description": "Сервисные операции с базой данных.",
}

@router.post(
    path="/db/init",
    tags=["db"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = SuccessSchema,
    description = db_init_descr
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
    description = db_initial_sync_descr
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
    description = db_regular_sync_descr
)
async def regular_sync(
    data: DBRegularSyncSchema,
    db_service: DBService = Depends(get_service_db)
) -> dict[str, Any]:
    message = await db_service.regular_sync(data)
    return {'message': message}
