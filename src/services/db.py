from src.auth.manager import create_user
from src.config import SERVICE_TOKEN, BUILTIN_ADMIN_NAME, BUILTIN_ADMIN_EMAIL, BUILTIN_ADMIN_FIRSTNAME, \
    BUILTIN_ADMIN_LASTNAME
from src.database import models
from src.repositories.db import DBRepository
from src.schemas.db import DBInitSchema, DBInitialSyncSchema, DBRegularSyncSchema
from src.schemas.user import UserCreateSchema
from src.utils import enums
from src.utils.exceptions import BadRequestException
from src.utils.password_policy import test_password_strength


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

        # Очищаем таблицы БД
        self.logger.info('Начинаю удаление данных из таблиц БД')
        await self.repository.delete_all(models.Log)
        await self.repository.delete_all(models.LogType)
        await self.repository.delete_all(models.Transaction)
        await self.repository.delete_all(models.OuterGoods)
        await self.repository.delete_all(models.InnerGoods)
        await self.repository.delete_all(models.CardSystem)
        await self.repository.delete_all(models.System)
        await self.repository.delete_all(models.Card)
        await self.repository.delete_all(models.CarDriver)
        await self.repository.delete_all(models.Car)
        await self.repository.delete_all(models.CardType)
        await self.repository.delete_all(models.AdminCompany)
        await self.repository.delete_all(models.User)
        await self.repository.delete_all(models.RolePermition)
        await self.repository.delete_all(models.Role)
        await self.repository.delete_all(models.Permition)
        await self.repository.delete_all(models.TariffHistory)
        await self.repository.delete_all(models.Company)
        await self.repository.delete_all(models.Tariff)

        # Создание типов карт
        await self.repository.init_card_types()

        # Создание ролей
        await self.repository.init_roles()

        # Получаем роль суперадмина
        role = await self.repository.get_cargo_superadmin_role()

        # Создание суперадмина
        user_schema = UserCreateSchema(
            username = BUILTIN_ADMIN_NAME,
            password = data.superuser_password,
            first_name = BUILTIN_ADMIN_FIRSTNAME,
            last_name = BUILTIN_ADMIN_LASTNAME,
            email = BUILTIN_ADMIN_EMAIL,
            phone = '',
            is_active = True,
            role_id = role.id
        )
        await create_user(user_schema)

    async def calculate_company_balance(self, company: models.Company, transactions) -> None:
        if transactions:
            # Формируем историю баланса
            previous_transaction = transactions[0]
            previous_transaction.company_balance = company.balance
            i = 1
            length = len(transactions)
            dataset = [{
                'id': transactions[0].id,
                'company_balance': transactions[0].company_balance,
            }]
            while i < length:
                transactions[i].company_balance = previous_transaction.company_balance - previous_transaction.total_sum
                previous_transaction = transactions[i]
                dataset.append({
                    'id': transactions[i].id,
                    'company_balance': transactions[i].company_balance,
                })
                i += 1

            # Обновляем записи в БД
            await self.repository.bulk_update(models.Transaction, dataset)

    async def calculate_balances(self) -> None:
        # Получаем список организаций
        companies = await self.repository.get_companies()

        # По каждой организации получаем список транзакций, текущий баланс применяем к самой
        # свежей транзакции. В обратном порядке следования транзакций формируем историю баланса.
        for company in companies:
            # Получаем транзакции этой организации
            transactions = await self.repository.get_company_transactions(company)

            # Вычисляем балансы
            await self.calculate_company_balance(company, transactions)

    async def initial_sync(self, data: DBInitialSyncSchema) -> None:
        # Проверка инициализационного токена
        if data.service_token != SERVICE_TOKEN:
            raise BadRequestException('Некорректный токен')

        # Очищаем таблицы БД
        self.logger.info('Начинаю удаление данных из таблиц БД')

        self.logger.info('Удаляю транзакции')
        await self.repository.delete_all(models.Transaction)
        self.logger.info('  -> выполнено')

        self.logger.info('Удаляю товары/услуги')
        await self.repository.delete_all(models.OuterGoods)
        await self.repository.delete_all(models.InnerGoods)
        self.logger.info('  -> выполнено')

        self.logger.info('Удаляю топливные карты')
        await self.repository.delete_all(models.CardSystem)
        await self.repository.delete_all(models.Card)
        self.logger.info('  -> выполнено')

        self.logger.info('Импортирую системы')
        await self.repository.import_systems(data.systems)

        self.logger.info('Импортирую тарифы')
        await self.repository.import_tariffs(data.tariffs)

        self.logger.info('Импортирую организации')
        await self.repository.import_companies(data.companies)

        self.logger.info('Импортирую автомобили')
        await self.repository.import_cars(data.cars)

        self.logger.info('Импортирую топливные карты')
        await self.repository.import_cards(data.cards)
        await self.repository.import_card_systems(data.cards)

        self.logger.info('Импортирую товары/услуги')
        await self.repository.import_inner_goods(data.goods, data.transactions)
        await self.repository.import_outer_goods(data.goods, data.transactions)

        self.logger.info('Импортирую транзакции')
        await self.repository.import_transactions(data.transactions)

        self.logger.info('Пересчитываю балансы')
        await self.calculate_balances()

    async def regular_sync(self, data: DBRegularSyncSchema) -> str:
        # Проверка инициализационного токена
        if data.service_token != SERVICE_TOKEN:
            raise BadRequestException('Некорректный токен')

        self.logger.info('Импортирую организации')
        companies_amount = await self.repository.sync_companies(data.companies)

        message = f'Импортировано новых организаций: {companies_amount} шт'
        return message
