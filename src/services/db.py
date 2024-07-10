from src.auth.manager import create_user
from src.config import SERVICE_TOKEN, BUILTIN_ADMIN_NAME, BUILTIN_ADMIN_FIRSTNAME, BUILTIN_ADMIN_LASTNAME, \
    BUILTIN_ADMIN_EMAIL
from src.database import models
from src.database.models import Base
from src.repositories.db.db import DBRepository
from src.schemas.db import DBInitSchema, DBInitialSyncSchema, DBRegularSyncSchema
from src.schemas.user import UserCreateSchema
from src.utils import enums
from src.utils.exceptions import BadRequestException, ApiError
from src.utils.password_policy import test_password_strength

from sqlalchemy import delete as sa_delete


class DBService:

    def __init__(self, repository: DBRepository) -> None:
        self.repository = repository
        self.logger = repository.logger

    def check_token(self, token: str) -> None:
        if token != SERVICE_TOKEN:
            raise BadRequestException('Некорректный токен')

    async def clear_tables(self) -> None:
        self.logger.info('Начинаю удаление данных из таблиц БД')
        metadata = Base.metadata
        counter = 1
        success = True
        table_names = list(metadata.tables.keys())
        tables = dict(metadata.tables)
        while True:
            print('-----------------------')
            print('Цикл:', counter)
            i = 0
            while i < len(table_names):
                table_name = table_names[i]
                table = tables[table_name]
                try:
                    stmt = sa_delete(table)
                    await self.repository.session.execute(stmt)
                    await self.repository.session.commit()
                except Exception as e:
                    await self.repository.session.rollback()
                    print('Не удалось удалить данные из таблицы', table_name)
                    print(e)
                    success = False
                    i += 1
                    continue
                else:
                    print('Успешно удалены данные из таблицы', table_name)
                    table_names.remove(table_name)

            counter += 1
            if success or counter == 5:
                break
            else:
                success = True

    async def create_superadmin(self, password: str) -> None:
        # Получаем роль суперадмина
        role = await self.repository.get_cargo_superadmin_role()

        # Создание суперадмина
        user_schema = UserCreateSchema(
            username=BUILTIN_ADMIN_NAME,
            password=password,
            first_name=BUILTIN_ADMIN_FIRSTNAME,
            last_name=BUILTIN_ADMIN_LASTNAME,
            email=BUILTIN_ADMIN_EMAIL,
            phone='',
            is_active=True,
            role_id=role.id
        )
        await create_user(user_schema)

    async def init_tables(self) -> None:
        # Создание типов карт
        await self.repository.init_card_types()

        # Создание ролей
        await self.repository.init_roles()

    async def db_init(self, data: DBInitSchema) -> None:

        # Проверка инициализационного токена
        self.check_token(data.service_token)

        # Проверка сложности пароля
        test_password_strength(enums.Role.CARGO_SUPER_ADMIN.name, data.superuser_password)

        # Очищаем таблицы БД
        await self.clear_tables()
        
        # Заполняем таблицы начальными данными
        await self.init_tables()

        # Создание суперадмина
        await self.create_superadmin(data.superuser_password)

    async def calculate_balance(self, balance: models.Balance, transactions) -> None:
        if transactions:
            # Формируем историю баланса
            previous_transaction = transactions[0]
            previous_transaction.contract_balance = balance.balance
            i = 1
            length = len(transactions)
            dataset = [{
                'id': transactions[0].id,
                'company_balance': transactions[0].contract_balance,
            }]
            while i < length:
                transactions[i].contract_balance = previous_transaction.contract_balance - previous_transaction.total_sum
                previous_transaction = transactions[i]
                dataset.append({
                    'id': transactions[i].id,
                    'company_balance': transactions[i].contract_balance,
                })
                i += 1

            # Обновляем записи в БД
            await self.repository.bulk_update(models.Transaction, dataset)

    async def calculate_balances(self) -> None:
        # Получаем балансы организаций
        balances = await self.repository.get_balances()

        # По каждому балансу получаем список транзакций, текущий баланс применяем к самой
        # свежей транзакции. В обратном порядке следования транзакций формируем историю баланса.
        for balance in balances:
            # Получаем транзакции этой организации
            transactions = await self.repository.get_balance_transactions(balance)

            # Вычисляем балансы
            await self.calculate_balance(balance, transactions)

    async def nnk_initial_sync(self, data: DBInitialSyncSchema) -> None:
        # Проверка инициализационного токена
        if data.service_token != SERVICE_TOKEN:
            raise BadRequestException('Некорректный токен')

        try:
            await self.repository.nnk_initial_sync(data)

            self.logger.info('Пересчитываю балансы')
            await self.calculate_balances()

        except Exception:
            # Очищаем таблицы БД
            await self.clear_tables()

            # Заполняем таблицы начальными данными
            await self.init_tables()

            # Создание суперадмина
            await self.create_superadmin(data.superuser_password)

            raise ApiError(trace=True, message='Ошибка выполнения процедуры первичной синхронизации')

    async def regular_sync(self, data: DBRegularSyncSchema) -> str:
        # Проверка инициализационного токена
        if data.service_token != SERVICE_TOKEN:
            raise BadRequestException('Некорректный токен')

        self.logger.info('Импортирую организации')
        companies_amount = await self.repository.sync_companies(data.companies)

        message = f'Импортировано новых организаций: {companies_amount} шт'
        return message
