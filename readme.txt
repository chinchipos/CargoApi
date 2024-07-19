alembic revision --autogenerate -m "Deleted fields LOGIN, PASSWORD, CONTRACT_NUM from table SYSTEM"
alembic upgrade head

Этот запрос починит проблему когда Алембик создает свою таблицу не в дефолтной схеме,
создает дебликаты типов (ENUM) и вообще ведет себя странно.
https://stackoverflow.com/a/74311722/23518799
alter user cargonomica set search_path = 'public';

После выполнения скрипта нужно пересоздать объекты БД:
SELECT 'DROP TABLE IF EXISTS ' || schemaname || '.' || tablename || ' CASCADE;'
FROM pg_tables
WHERE schemaname IN ('cargonomica', 'public');
