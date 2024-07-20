from typing import List, Dict

import asyncio

from celery import Celery, chord, chain

redis_server = 'redis://localhost:6379'
celery = Celery('cargonomica', backend=redis_server, broker=f'{redis_server}/0')
celery.conf.broker_connection_retry_on_startup = True


async def async_task1():
    await asyncio.sleep(5)
    return {"tr_khnp1": 1}


async def async_task2():
    await asyncio.sleep(5)
    return {"tr_noname": 1}


# ХНП
@celery.task(name="SYNC_CARDS_KHNP")
def sync_cards_khnp():
    try:
        asyncio.run(async_task1())
    except Exception:
        pass


@celery.task(name="SYNC_TRANSACTIONS_KHNP")
def sync_transactions_khnp():
    try:
        return asyncio.run(async_task1())
    except Exception:
        pass


# Noname
@celery.task(name="SYNC_CARDS_NONAME")
def sync_cards_noname():
    try:
        asyncio.run(async_task2())
    except Exception:
        pass


@celery.task(name="SYNC_TRANSACTIONS_NONAME")
def sync_transactions_noname():
    try:
        return asyncio.run(async_task2())
    except Exception:
        pass


# Агрегированные методы
@celery.task(name="AGREGATE_SYNC_TRANSACTIONS")
def agregate_sync_transactions(params: List[Dict[str, int]]):
    new_dict = params[0] | params[1]
    return new_dict


@celery.task(name="CALC_OVERDRAFTS")
def calc_overdrafts(x: Dict[str, int]):
    return x


@celery.task(name="CALC_BALANCES")
def calc_balances(x: Dict[str, int]):
    return x


# Модель запуска задач.

# Этапы выполнения:
# 1. Синхронизация карт.
# 2. Синхронизация транзакций за период (зависит от п.1 этой же системы)
# 3. Пересчет овердрафтов за период (запускается после выполнения п.2 по всем системам)
# 4. Пересчет балансов за период (запускается после выполнения п.3)

# Цепочка: "Синхронизация карт ХНП" <-> "Синхронизация транзакций ХНП"
sync_cars_and_transactions_khnp = chain(
    sync_cards_khnp.si(),
    sync_transactions_khnp.si()
)

# Цепочка: "Синхронизация карт Noname" <-> "Синхронизация транзакций Noname"
sync_cars_and_transactions_noname = chain(
    sync_cards_noname.si(),
    sync_transactions_noname.si()
)

# Агрегирование цепочек "Синхронизация карт" <-> "Синхронизация транзакций"
sync_cars_and_transactions = chord(
    header=[
        sync_cars_and_transactions_khnp,
        sync_cars_and_transactions_noname
    ],
    body=agregate_sync_transactions.s()
)

# Результирующая цепочка:
# "Агрегация (карты-транзакции)" <-> "Пересчет овердрафтов" <-> "Пересчет балансов"
main_sync_chain = chain(
    sync_cars_and_transactions,
    calc_overdrafts.s(),
    calc_balances.s()
)
