import asyncio
import sys

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import PROD_URI, GOODS_FILE_PATH
from src.database.db import DatabaseSessionManager
from src.database.models import OuterGoodsGroupOrm, OuterGoodsOrm
from src.database.models.goods_category import OuterGoodsCategoryOrm
from src.repositories.goods import GoodsRepository
from src.repositories.system import SystemRepository
from src.utils.enums import ContractScheme
from src.utils.loggers import get_logger

_logger = get_logger(name="GpnGoodsImporter", filename="celery.log")


async def process_categories(imported_data: pd.DataFrame, goods_repository: GoodsRepository, gpn_system_id: str):
    # Получаем категории продуктов из БД
    db_categories = await goods_repository.get_outer_categories()
    db_category_external_ids = [db_category.external_id for db_category in db_categories]

    # Получаем мпортируемые категории продуктов
    imported_categories = imported_data[["GOODS_CATEGORY_CODE", "GOODS_CATEGORY"]].drop_duplicates()

    # Сравниваем импортируемые данные с сохраненными. Новые записываем в БД.
    def has_equal_in_db(category_code: str):
        return category_code in db_category_external_ids

    new_categories = []
    for index, row in imported_categories.iterrows():
        if not has_equal_in_db(row["GOODS_CATEGORY_CODE"]):
            new_categories.append({
                "external_id": row["GOODS_CATEGORY_CODE"],
                "name": row["GOODS_CATEGORY"],
                "system_id": gpn_system_id
            })

    if new_categories:
        await goods_repository.bulk_insert_or_update(OuterGoodsCategoryOrm, new_categories)
        _logger.info(f"Количество новых категорий {len(new_categories)}")
    else:
        _logger.info("Новых категорий нет")


async def process_groups(imported_data: pd.DataFrame, goods_repository: GoodsRepository, gpn_system_id: str):
    # Получаем категории продуктов из БД
    db_categories = await goods_repository.get_outer_categories()

    # Получаем группы продуктов из БД
    db_groups = await goods_repository.get_outer_groups()
    db_group_external_ids = [db_group.external_id for db_group in db_groups]

    # Получаем мпортируемые группы продуктов
    imported_groups = imported_data[["GOODS_CATEGORY_CODE", "GOODS_GROUP_CODE", "GOODS_GROUP"]].drop_duplicates()

    # Сравниваем импортируемые данные с сохраненными. Новые записываем в БД.
    def has_equal_in_db(group_code: str) -> bool:
        return group_code in db_group_external_ids

    def get_category_id(category_code: str) -> str:
        for db_category in db_categories:
            if db_category.external_id == category_code:
                return db_category.id

    new_groups = []
    for index, row in imported_groups.iterrows():
        if not has_equal_in_db(row["GOODS_GROUP_CODE"]):
            new_groups.append({
                "external_id": row["GOODS_GROUP_CODE"],
                "name": row["GOODS_GROUP"],
                "system_id": gpn_system_id,
                "outer_category_id": get_category_id(row["GOODS_CATEGORY_CODE"])
            })

    if new_groups:
        await goods_repository.bulk_insert_or_update(OuterGoodsGroupOrm, new_groups)
        _logger.info(f"Количество новых групп {len(new_groups)}")
    else:
        _logger.info("Новых групп нет")


async def process_goods(imported_data: pd.DataFrame, goods_repository: GoodsRepository, gpn_system_id: str):
    # Получаем группы продуктов из БД
    db_groups = await goods_repository.get_outer_groups()

    # Получаем продукты из БД
    db_goods = await goods_repository.get_outer_goods()
    db_goods_external_ids = [db_goods_item.external_id for db_goods_item in db_goods]

    # Получаем мпортируемые продукты
    imported_goods = imported_data[["GOODS_CATEGORY", "GOODS_GROUP_CODE", "GOODS_CODE", "GOODS"]].drop_duplicates()

    # Сравниваем импортируемые данные с сохраненными. Новые записываем в БД.
    def has_equal_in_db(goods_code: str) -> bool:
        return goods_code in db_goods_external_ids

    def get_group_id(category_code: str) -> str:
        for db_group in db_groups:
            if db_group.external_id == category_code:
                return db_group.id

    new_goods = []
    for index, row in imported_goods.iterrows():
        # if not has_equal_in_db(row["GOODS_CODE"]) and row["GOODS_CATEGORY"] == "Топливо":
        if not has_equal_in_db(row["GOODS_CODE"]):
            new_goods.append({
                "external_id": row["GOODS_CODE"],
                "name": row["GOODS"],
                "system_id": gpn_system_id,
                "outer_group_id": get_group_id(row["GOODS_GROUP_CODE"])
            })

    if new_goods:
        await goods_repository.bulk_insert_or_update(OuterGoodsOrm, new_goods)
        _logger.info(f"Количество новых продуктов {len(new_goods)}")
    else:
        _logger.info("Новых продуктов нет")


async def import_goods(session: AsyncSession):
    # Считываем информацию из файла
    imported_data = pd.read_excel(GOODS_FILE_PATH)
    length = len(imported_data)
    _logger.info(f"Файл прочитан успешно. Количество записей: {length}")

    goods_repository = GoodsRepository(session=session, user=None)
    system_repository = SystemRepository(session=session, user=None)

    gpn_system = await system_repository.get_system_by_short_name(
        system_fhort_name='ГПН',
        scheme=ContractScheme.OVERBOUGHT
    )

    # Обрабатываем категории продуктов
    # await process_categories(imported_data, goods_repository, gpn_system.id)

    # Обрабатываем группы продуктов
    # await process_groups(imported_data, goods_repository, gpn_system.id)

    # Обрабатываем продукты
    await process_goods(imported_data, goods_repository, gpn_system.id)


async def gpn_goods_import_fn() -> None:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        await import_goods(session)

    # Закрываем соединение с БД
    await sessionmanager.close()


def gpn_goods_import() -> None:
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(gpn_goods_import_fn())
