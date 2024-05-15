from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse

from src.auth.auth import auth_backend, fastapi_users
from src.database.db import engine
from src.routing.db import router as db_routing, db_tag_metadata
from src.routing.user import router as user_routing, user_tag_metadata
from src.routing.system import router as system_routing, system_tag_metadata
from src.routing.company import router as company_routing, company_tag_metadata
from src.routing.tariff import router as tariff_routing, tariff_tag_metadata
from src.routing.card_type import router as card_type_routing, card_type_tag_metadata
from src.routing.card import router as card_routing, card_tag_metadata
from src.schemas.user import UserReadSchema, UserCreateSchema
from src.utils.exceptions import BadRequestException, ForbiddenException, DBException, DBDuplicateException
from src.utils.log import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info('APP START')
    yield
    print('APP SHUTDOWN')
    await engine.dispose()

tags_metadata = [
    {
        "name": "auth",
        "description": 'Операции аутентификации и смены пароля.',
    },
    db_tag_metadata,
    user_tag_metadata,
    system_tag_metadata,
    company_tag_metadata,
    tariff_tag_metadata,
    card_type_tag_metadata,
    card_tag_metadata,
]

app = FastAPI(
    lifespan=lifespan,
    openapi_tags=tags_metadata
)
app.include_router(db_routing)
app.include_router(user_routing)
app.include_router(system_routing)
app.include_router(company_routing)
app.include_router(tariff_routing)
app.include_router(card_type_routing)
app.include_router(card_routing)
app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_register_router(UserReadSchema, UserCreateSchema),
    prefix="/auth",
    tags=["auth"],
)


@app.get("/docs", include_in_schema=False)
async def get_documentation(request: Request):
    print(request.scope)
    print('jhjhfjgfjgf')
    return get_swagger_ui_html(openapi_url=request.scope.get("root_path") + "/openapi.json", title="Документация")


@app.exception_handler(BadRequestException)
async def bad_request_exception_handler(request: Request, exc: BadRequestException):
    return JSONResponse(
        status_code = 400,
        content = {"message": exc.message},
    )


@app.exception_handler(ForbiddenException)
async def forbidden_exception_handler(request: Request, exc: ForbiddenException):
    return JSONResponse(
        status_code = 403,
        content = {"message": exc.message},
    )


@app.exception_handler(DBException)
async def bad_request_exception_handler(request: Request, exc: BadRequestException):
    return JSONResponse(
        status_code = 400,
        content = {"message": exc.message},
    )


@app.exception_handler(DBDuplicateException)
async def bad_request_exception_handler(request: Request, exc: BadRequestException):
    return JSONResponse(
        status_code = 400,
        content = {"message": exc.message},
    )
