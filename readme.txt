alembic revision --autogenerate -m "Deleted fields LOGIN, PASSWORD, CONTRACT_NUM from table SYSTEM"
alembic upgrade head

---------------------------------------
Этот запрос починит проблему когда Алембик создает свою таблицу не в дефолтной схеме,
создает дубликаты типов (ENUM) и вообще ведет себя странно.
https://stackoverflow.com/a/74311722/23518799
alter user cargonomica set search_path = 'public';

После выполнения скрипта нужно пересоздать объекты БД:
SELECT 'DROP TABLE IF EXISTS ' || schemaname || '.' || tablename || ' CASCADE;'
FROM pg_tables
WHERE schemaname IN ('cargonomica', 'public');

ENUM автоматически не добавляется. Нужно править файл ревизии Алембика. Пример рабочего кода:
sa.Enum('MANUALLY', 'PIN', name='blockingcardreason').create(op.get_bind())
op.add_column('card', sa.Column('reason_for_blocking', postgresql.ENUM('MANUALLY', 'PIN', name='blockingcardreason',
    create_type=False), nullable=True, comment='Причина блокировки карты'), schema='cargonomica')

---------------------------------------
pytest tests/ -rx --log-disable=main
