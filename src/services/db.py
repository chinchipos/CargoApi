from src.auth.manager import create_user
from src.config import SERVICE_TOKEN
from src.database.models import Transaction, OuterGoods, InnerGoods, CardSystem, Card, Company
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

    async def calculate_company_balance(self, company: Company, transactions) -> None:
        if transactions:
            # Формируем историю баланса
            previous_transaction = transactions[0]
            previous_transaction.company_balance_after = company.current_balance
            i = 1
            length = len(transactions)
            dataset = [{
                'id': transactions[0].id,
                'company_balance_after': transactions[0].company_balance_after,
            }]
            while i < length:
                transactions[i].company_balance_after = previous_transaction.company_balance_after - \
                                                        previous_transaction.total_sum
                previous_transaction = transactions[i]
                dataset.append({
                    'id': transactions[i].id,
                    'company_balance_after': transactions[i].company_balance_after,
                })
                i += 1

            # Обновляем записи в БД
            await self.repository.bulk_update(Transaction, dataset)

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
        await self.repository.delete_all(Transaction)
        self.logger.info('  -> выполнено')

        self.logger.info('Удаляю товары/услуги')
        await self.repository.delete_all(OuterGoods)
        await self.repository.delete_all(InnerGoods)
        self.logger.info('  -> выполнено')

        self.logger.info('Удаляю топливные карты')
        await self.repository.delete_all(CardSystem)
        await self.repository.delete_all(Card)
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

    async def regular_sync(self, data: DBRegularSyncSchema) -> None:
        # Проверка инициализационного токена
        if data.service_token != SERVICE_TOKEN:
            raise BadRequestException('Некорректный токен')
