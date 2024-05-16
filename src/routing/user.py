from fastapi import APIRouter, Depends

from src.database import models
from src.depends import get_service_user
from src.schemas.user import UserReadSchema
from src.services.user import UserService
from src.utils.descriptions.user import user_tag_description, get_me_description
from src.utils.schemas import MessageSchema


router = APIRouter()
user_tag_metadata = {
    "name": "user",
    "description": user_tag_description,
}

@router.get(
    path="/user/me",
    tags=["user"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = UserReadSchema,
    description = get_me_description
)
async def get_me(
    user_service: UserService = Depends(get_service_user)
) -> models.User:
    user = await user_service.get_me()
    return user
