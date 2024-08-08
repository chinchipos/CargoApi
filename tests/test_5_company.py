from datetime import date
import random

import pytest
from httpx import AsyncClient
from sqlalchemy import select as sa_select

from src.database.db import sessionmanager
from src.database.model.models import Tariff, Company
from src.repositories.base import BaseRepository


@pytest.mark.incremental
@pytest.mark.order(5)
class TestSystem:

    """
    Создание записи
    """

    # Создаем новые организации
    async def test_create_company(self, aclient: AsyncClient, token: str):
        async with sessionmanager.session() as session:
            # Получаем тарифы
            repository = BaseRepository(session, None)
            stmt = sa_select(Tariff).where(Tariff.name.in_(["Полпроцента", "Полтора процента", "Два процента"]))
            tariffs = await repository.select_all(stmt)

            # Создаем организации
            names = ['ООО "Рога и Копыта"', 'ООО "Ромашка"', 'ООО "Дильшот Логистикс"']
            balances = [10000, 20000, 30000]
            inns = ["111111111111", "222222222222", "333333333333"]
            dataset = [
                {
                    "name": names[i],
                    "date_add": date.today(),
                    "tariff_id": tariffs[i].id,
                    "personal_account": ('000000' + str(random.randint(1, 9999999)))[-7:],
                    "inn": inns[i],
                    "balance": balances[i],
                    "min_balance": 0,
                    "min_balance_period_end_date": None,
                    "min_balance_on_period": 0,
                } for i in range(3)
            ]
            await repository.bulk_insert_or_update(Company, dataset)

            stmt = sa_select(Company)
            companies = await repository.select_all(stmt)

            msg = "Не удалось создать организации"
            assert len(companies) == 3, msg
