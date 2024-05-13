from fastapi import APIRouter, Depends

from src.database import models
from src.depends import get_service_user
from src.schemas.user import UserReadSchema
from src.services.user import UserService
from src.utils.schemas import MessageSchema


router = APIRouter(prefix="/user/me", tags=["user"])
user_tag_metadata = {
    "name": "user",
    "description": 'Операции с объектом "Пользователь".',
}

@router.get(
    "",
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = UserReadSchema,
    description = (
        """
        Получение собственного профиля.<br>
        <br>
        Входные параметры отсутствуют.
        """
    ),
)
async def get_me(
    user_service: UserService = Depends(get_service_user)
) -> models.User:
    user = await user_service.get_me()
    return user
