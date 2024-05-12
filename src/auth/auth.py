import uuid

from fastapi_users.authentication import BearerTransport, AuthenticationBackend
from fastapi_users.authentication import JWTStrategy
from fastapi_users import FastAPIUsers

from src.auth.manager import get_user_manager
from src.database.models import User

from src.config import JWT_SECRET

bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")
SECRET = JWT_SECRET


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=SECRET,
        lifetime_seconds=3600
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
