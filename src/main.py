from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src import config
from src.auth.auth import auth_backend, fastapi_users
from src.config import PROD_URI
from src.database.db import sessionmanager
from src.routing.car import router as car_routing, car_tag_metadata
from src.routing.card import router as card_routing, card_tag_metadata
from src.routing.card_type import router as card_type_routing, card_type_tag_metadata
from src.routing.company import router as company_routing, company_tag_metadata
from src.routing.db import router as db_routing, db_tag_metadata
from src.routing.role import router as role_routing, role_tag_metadata
from src.routing.system import router as system_routing, system_tag_metadata
from src.routing.tariff import router as tariff_routing, tariff_tag_metadata
from src.routing.transaction import router as transaction_routing, transaction_tag_metadata
from src.routing.goods import router as goods_routing, goods_tag_metadata
from src.routing.user import router as user_routing, user_tag_metadata
from src.utils.exceptions import BadRequestException, ForbiddenException, DBException, DBDuplicateException, ApiError
from src.utils.log import logger

# from fastapi_cache import FastAPICache
# from fastapi_cache.backends.redis import RedisBackend

# from redis import asyncio as aioredis


def init_app(dsn: str, tests: bool = False):
    sessionmanager.init(dsn, tests)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        logger.info('APP START')
        # redis = aioredis.from_url("redis://localhost")
        # FastAPICache.init(RedisBackend(redis), prefix="fastapi-cache")
        yield
        print('APP SHUTDOWN')
        await sessionmanager.close()  # dispose()

    tags_metadata = [
        {
            "name": "auth",
            "description": 'Аутентификация, авторизация, смена пароля.',
        },
        db_tag_metadata,
        user_tag_metadata,
        system_tag_metadata,
        company_tag_metadata,
        tariff_tag_metadata,
        card_type_tag_metadata,
        card_tag_metadata,
        transaction_tag_metadata,
        car_tag_metadata,
        role_tag_metadata,
        goods_tag_metadata,
    ]

    app = FastAPI(
        title="Cargonomica API",
        lifespan=lifespan,
        openapi_tags=tags_metadata,
        root_path="/api",
        docs_url="/doc",
        redoc_url=None,
        openapi_url="/openapi.json",
        swagger_ui_parameters={
            "defaultModelsExpandDepth": -1,
            "defaultModelExpandDepth": 4
        }
    )

    @app.get("/")
    async def read_root():
        return {"message": "Cargonomica API"}

    app.include_router(db_routing)
    app.include_router(user_routing)
    app.include_router(system_routing)
    app.include_router(company_routing)
    app.include_router(tariff_routing)
    app.include_router(card_type_routing)
    app.include_router(card_routing)
    app.include_router(transaction_routing)
    app.include_router(car_routing)
    app.include_router(role_routing)
    app.include_router(goods_routing)
    app.include_router(
        fastapi_users.get_auth_router(auth_backend),
        prefix="/auth/jwt",
        tags=["auth"],
    )

    # app.include_router(
    #     fastapi_users.get_register_router(NewUserReadSchema, UserCreateSchema),
    #     prefix="/auth",
    #     tags=["auth"],
    # )

    for route in app.routes:
        if route.__dict__['path'] == '/auth/jwt/login':
            route.__dict__['summary'] = 'Вход в систему'

        if route.__dict__['path'] == '/auth/jwt/logout':
            route.__dict__['summary'] = 'Выход из системы'

        # if route.__dict__['path'] == '/auth/register':
        #     route.__dict__['summary'] = 'Создание пользователя'

    @app.exception_handler(BadRequestException)
    async def bad_request_exception_handler(request: Request, exc: BadRequestException):
        return JSONResponse(
            status_code=400,
            content={"message": exc.message},
        )

    @app.exception_handler(ForbiddenException)
    async def forbidden_exception_handler(request: Request, exc: ForbiddenException):
        return JSONResponse(
            status_code=403,
            content={"message": exc.message},
        )

    @app.exception_handler(DBException)
    async def bad_request_exception_handler(request: Request, exc: BadRequestException):
        return JSONResponse(
            status_code=400,
            content={"message": exc.message},
        )

    @app.exception_handler(DBDuplicateException)
    async def bad_request_exception_handler(request: Request, exc: BadRequestException):
        return JSONResponse(
            status_code=400,
            content={"message": exc.message},
        )

    @app.exception_handler(ApiError)
    async def api_exception_handler(request: Request, exc: BadRequestException):
        return JSONResponse(
            status_code=400,
            content={"message": exc.message},
        )

    return app


app = init_app(PROD_URI)
