import traceback
import uuid

from fastapi import Depends
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import BearerTransport, AuthenticationBackend
from fastapi_users.authentication import JWTStrategy
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.auth.manager import get_user_manager
from src.config import JWT_SECRET
from src.database.db import get_session
from src.database.model.models import User
from src.utils.exceptions import DBException
from src.utils.log import logger

bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")
SECRET = JWT_SECRET


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=SECRET,
        lifetime_seconds=7200
    )


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)


current_active_user = fastapi_users.current_user(active=True)


async def get_current_active_user(
        session: AsyncSession = Depends(get_session),
        user: User = Depends(current_active_user)
):
    try:
        stmt = (
            sa_select(User)
            .options(joinedload(User.role))
            .where(User.id == user.id)
            .limit(1)
        )
        result = await session.scalars(
            stmt,
            execution_options={"populate_existing": True}
        )
        user_db = result.first()
        return user_db

    except Exception:
        logger.error(traceback.format_exc())
        raise DBException()
