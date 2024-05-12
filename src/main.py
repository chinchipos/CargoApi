from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.auth.auth import auth_backend, fastapi_users
from src.database.db import engine
from src.routing.author import router as author_routing
from src.routing.book import router as book_routing
from src.routing.db import router as db_sync_routing, db_tag_metadata
from src.routing.user import router as user_routing, user_tag_metadata
from src.schemas.user import UserReadSchema, UserCreateSchema
from src.utils.exceptions import BadRequestException, ForbiddenException
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
]

app = FastAPI(lifespan=lifespan, openapi_tags=tags_metadata)
app.include_router(author_routing)
app.include_router(book_routing)
app.include_router(db_sync_routing)
app.include_router(user_routing)
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
