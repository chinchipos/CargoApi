from src.auth.manager import create_user
from src.config import SERVICE_TOKEN
from src.database.models import Transaction, OuterGoods, InnerGoods, CardSystem, Card
from src.repositories.db import DBRepository
from src.schemas.db import DBInitSchema, DBInitialSyncSchema, DBRegularSyncSchema
from src.schemas.user import UserCreateSchema
from src.utils.exceptions import BadRequestException
from src.utils.password_policy import test_password_strength
from src.utils import enums


class DBService:

    def __init__(self, repository: DBRepository) -> None:
        self.repository = repository
        self.logger = repository.logger

    async def init(self, data: DBInitSchema) -> None:
        # Проверка инициализационного токена
        if data.service_token != SERVICE_TOKEN:
            raise BadRequestException('Некорректный токен')

        # Проверка сложности пароля
        test_password_strength(enums.Role.CARGO_SUPER_ADMIN.name, data.superuser_password)

        # Создание ролей
        await self.repository.init_roles()

        # Получаем роль суперадмина
        role = await self.repository.get_cargo_superadmin_role()

        # Создание суперадмина
        # user_repository = UserRepository(self.repository.session, None)
        user_schema = UserCreateSchema(
            username = 'cargo',
            password = data.superuser_password,
            first_name = 'Администратор',
            last_name = 'Главный',
            email = 'cargo@cargonomica.com',
            phone = '',
            role_id = role.id
        )
        # await user_repository.create_user(user_schema)
        await create_user(user_schema)

        # Создание типов карт
        await self.repository.init_card_types()

    async def initial_sync(self, data: DBInitialSyncSchema) -> None:
        # Проверка инициализационного токена
        if data.service_token != SERVICE_TOKEN:
            raise BadRequestException('Некорректный токен')

        # Очищаем таблицы БД
        self.logger.info('Начинаю удаление данных из таблиц БД')

        self.logger.info('Удаляю транзакции')
        await self.repository.delete_all(Transaction)
        self.logger.info('      -> выполнено')

        self.logger.info('Удаляю товары/услуги')
        await self.repository.delete_all(OuterGoods)
        await self.repository.delete_all(InnerGoods)
        self.logger.info('      -> выполнено')

        self.logger.info('Удаляю топливные карты')
        await self.repository.delete_all(CardSystem)
        await self.repository.delete_all(Card)
        self.logger.info('      -> выполнено')

    async def regular_sync(self, data: DBRegularSyncSchema) -> None:
        # Проверка инициализационного токена
        if data.service_token != SERVICE_TOKEN:
            raise BadRequestException('Некорректный токен')
