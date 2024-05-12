from src.database import models
from src.database.models import User
from src.repositories.user import UserRepository


class UserService:

    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    async def get_me(self) -> models.User:
        me = await self.repository.get_user(self.repository.user.id)
        return me
