import asyncio
import sys
from typing import Any

from src.celery_app.balance.calc_balance import CalcBalances
from src.celery_app.exceptions import CeleryError
from src.celery_app.gpn.controller import GPNController
from src.celery_app.khnp.controller import KHNPController
from src.celery_app.ops.controller import OpsController
from src.config import PROD_URI
from src.database.db import DatabaseSessionManager


async def perform_actions(controller_name: str, func_name: str, **func_params) -> Any:
    sessionmanager = DatabaseSessionManager()
    sessionmanager.init(PROD_URI)

    async with sessionmanager.session() as session:
        # Создаем экземпляр класса контроллера
        if controller_name == "GPNController":
            controller = GPNController(session=session)
        elif controller_name == "OpsController":
            controller = OpsController(session=session)
        elif controller_name == "KHNPController":
            controller = KHNPController(session=session)
        elif controller_name == "CalcBalances":
            controller = CalcBalances(session=session)
        else:
            raise CeleryError(f"Не удалось создать экземпляр класса контроллера. "
                              f"Имя класса не опознано: {controller_name}.")

        # Инициализируем переменные класса, получаемые из БД асинхронными функциями
        await controller.init()

        # Выполняем запрошенную функцию
        func = getattr(controller, func_name)
        output = await func(**func_params)

    # Закрываем соединение с БД
    await sessionmanager.close()
    return output


def perform_controller_actions(controller_name: str, func_name: str, **func_params) -> Any:
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    return asyncio.run(perform_actions(controller_name, func_name, **func_params))
