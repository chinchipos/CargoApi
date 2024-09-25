from typing import Dict, List

from src.celery_app.async_helper import perform_controller_actions
from src.celery_app.gpn.api import GPNApi
from src.celery_app.irrelevant_balances import IrrelevantBalances
from src.celery_app.main import celery
from src.utils.loggers import get_logger

_logger = get_logger(name="GPN_TASKS", filename="celery.log")


# async def gpn_sync_fn() -> IrrelevantBalances:
#     sessionmanager = DatabaseSessionManager()
#     sessionmanager.init(PROD_URI)
#
#     async with sessionmanager.session() as session:
#         gpn = GPNController(session)
#         irrelevant_balances = await gpn.sync()
#
#     # Закрываем соединение с БД
#     await sessionmanager.close()
#
#     _logger.info('Синхронизация с ГПН успешно завершена')
#     return irrelevant_balances
#
#
# @celery.task(name="SYNC_GPN")
# def gpn_sync() -> IrrelevantBalances:
#     _logger.info("Запускаю синхронизацию с ГПН")
#     try:
#         return asyncio.run(gpn_sync_fn())
#
#     except Exception as e:
#         _logger.exception(str(e))
#         _logger.info("Ошибка синхронизации с ГПН")

@celery.task(name="SYNC_GPN")
def gpn_sync() -> IrrelevantBalances:
    _logger.info("Запускаю синхронизацию с ГПН")
    try:
        irrelevant_balances = perform_controller_actions(
            controller_name="GPNController",
            func_name="sync"
        )
        _logger.info("Завершена синхронизация с ГПН")
        return irrelevant_balances

    except Exception as e:
        _logger.exception(str(e))
        _logger.info("Ошибка синхронизации с ГПН")


# async def gpn_set_card_states_fn(balance_ids_to_change_card_states: Dict[str, List[str]]) -> None:
#     sessionmanager = DatabaseSessionManager()
#     sessionmanager.init(PROD_URI)
#
#     async with sessionmanager.session() as session:
#         gpn_controller = GPNController(session)
#         await gpn_controller.set_card_states(balance_ids_to_change_card_states)
#
#     # Закрываем соединение с БД
#     await sessionmanager.close()


# @celery.task(name="GPN_SET_CARD_STATES")
# def gpn_set_card_states(balance_ids_to_change_card_states: Dict[str, List[str]]) -> str:
#     if balance_ids_to_change_card_states["to_block"] or balance_ids_to_change_card_states["to_activate"]:
#         _logger.info('Запускаю задачу блокировки / разблокировки карт ГПН')
#
#         if sys.platform == 'win32':
#             asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
#
#         asyncio.run(gpn_set_card_states_fn(balance_ids_to_change_card_states))
#
#     else:
#         _logger.info('Блокировка / разблокировка карт не требуется: не было транзакций '
#                      'с момента последней синхронизации')
#
#     return "COMPLETE"

@celery.task(name="GPN_SET_CARD_STATES")
def gpn_set_card_states(balance_ids_to_change_card_states: Dict[str, List[str]]) -> str:
    if balance_ids_to_change_card_states["to_block"] or balance_ids_to_change_card_states["to_activate"]:
        _logger.info('Запускаю задачу блокировки / разблокировки карт ГПН')
        perform_controller_actions(
            controller_name="GPNController",
            func_name="set_card_states",
            balance_ids_to_change_card_states=balance_ids_to_change_card_states
        )
        _logger.info('Завершена задача блокировки / разблокировки карт ГПН')

    else:
        _logger.info('Блокировка / разблокировка карт не требуется: не было транзакций '
                     'с момента последней синхронизации')

    return "COMPLETE"


# async def service_sync_fn() -> None:
#     sessionmanager = DatabaseSessionManager()
#     sessionmanager.init(PROD_URI)
#
#     async with sessionmanager.session() as session:
#         gpn_controller = GPNController(session)
#         await gpn_controller.init_system()
#         await gpn_controller.service_sync()
#
#     # Закрываем соединение с БД
#     await sessionmanager.close()
#
#
# @celery.task(name="GPN_SERVICE_SYNC")
# def gpn_service_sync() -> None:
#     if sys.platform == 'win32':
#         asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
#
#     asyncio.run(service_sync_fn())

@celery.task(name="GPN_SERVICE_SYNC")
def gpn_service_sync() -> None:
    _logger.info('Запускаю задачу сервисной синхронизации с ГПН (модуль не доработан)')
    perform_controller_actions(
        controller_name="GPNController",
        func_name="service_sync"
    )
    _logger.info('Завершена задача сервисной синхронизации с ГПН (модуль не доработан)')


# async def gpn_issue_virtual_cards_fn(amount: int) -> None:
#     sessionmanager = DatabaseSessionManager()
#     sessionmanager.init(PROD_URI)
#
#     async with sessionmanager.session() as session:
#         gpn_controller = GPNController(session)
#         await gpn_controller.issue_virtual_cards(amount)
#
#     # Закрываем соединение с БД
#     await sessionmanager.close()
#
#
# @celery.task(name="GPN_ISSUE_VIRTUAL_CARDS")
# def gpn_issue_virtual_cards(amount: int) -> None:
#     if sys.platform == 'win32':
#         asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
#
#     asyncio.run(gpn_issue_virtual_cards_fn(amount))

@celery.task(name="GPN_ISSUE_VIRTUAL_CARDS")
def gpn_issue_virtual_cards(amount: int) -> None:
    _logger.info('Запускаю задачу выпуска виртуальных карт ГПН')
    perform_controller_actions(
        controller_name="GPNController",
        func_name="issue_virtual_cards",
        amount=amount
    )
    _logger.info('Завершена задача выпуска виртуальных карт ГПН')


@celery.task(name="GPN_SET_CARD_STATE")
def gpn_set_card_state(external_card_id: str, activate: bool) -> None:
    action = "разблокировки" if activate else "блокировки"
    _logger.info(f'Запускаю задачу {action} карты ГПН')
    gpn_api = GPNApi()
    if activate:
        gpn_api.activate_cards([external_card_id])
    else:
        gpn_api.block_cards([external_card_id])

    _logger.info(f'Завершена задача {action} карты ГПН')


# async def delete_card_limits_fn(limit_ids: List[str]) -> None:
#     sessionmanager = DatabaseSessionManager()
#     sessionmanager.init(PROD_URI)
#
#     async with sessionmanager.session() as session:
#         gpn_controller = GPNController(session)
#         await gpn_controller.delete_card_limits(limit_ids)
#
#     # Закрываем соединение с БД
#     await sessionmanager.close()
#
#
# @celery.task(name="GPN_DELETE_CARD_LIMITS")
# def gpn_delete_card_limits(limit_ids: List[str]) -> None:
#     if sys.platform == 'win32':
#         asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
#
#     asyncio.run(delete_card_limits_fn(limit_ids))

@celery.task(name="GPN_DELETE_CARD_LIMITS")
def gpn_delete_card_limits(limit_ids: List[str]) -> None:
    _logger.info('Запускаю задачу удаления карточных лимитов ГПН')
    perform_controller_actions(
        controller_name="GPNController",
        func_name="delete_card_limits",
        limit_ids=limit_ids
    )
    _logger.info('Завершена задача удаления карточных лимитов ГПН')

# async def create_card_limits_fn(company_id: str, card_external_id: str, limit_ids: List[str]) -> None:
#     sessionmanager = DatabaseSessionManager()
#     sessionmanager.init(PROD_URI)
#
#     async with sessionmanager.session() as session:
#         gpn_controller = GPNController(session)
#         await gpn_controller.set_card_limits(company_id, card_external_id, limit_ids)
#
#     # Закрываем соединение с БД
#     await sessionmanager.close()


# @celery.task(name="GPN_CREATE_CARD_LIMITS")
# def gpn_create_card_limits(company_id: str, card_external_id: str, limit_ids: List[str]) -> None:
#     if sys.platform == 'win32':
#         asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
#
#     asyncio.run(create_card_limits_fn(company_id, card_external_id, limit_ids))


@celery.task(name="GPN_CREATE_CARD_LIMITS")
def gpn_create_card_limits(company_id: str, card_external_id: str, limit_ids: List[str]) -> None:
    _logger.info('Запускаю задачу установки карточного лимита ГПН')
    perform_controller_actions(
        controller_name="GPNController",
        func_name="set_card_limits",
        company_id=company_id,
        card_external_id=card_external_id,
        limit_ids=limit_ids
    )
    _logger.info('Завершена задача установки карточного лимита ГПН')


# async def gpn_import_azs_fn() -> None:
#     sessionmanager = DatabaseSessionManager()
#     sessionmanager.init(PROD_URI)
#
#     async with sessionmanager.session() as session:
#         gpn_controller = GPNController(session)
#         await gpn_controller.import_azs()
#
#     # Закрываем соединение с БД
#     await sessionmanager.close()
#
#
# @celery.task(name="GPN_IMPORT_AZS")
# def gpn_import_azs() -> None:
#     if sys.platform == 'win32':
#         asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
#
#     asyncio.run(gpn_import_azs_fn())


@celery.task(name="GPN_IMPORT_AZS")
def gpn_import_azs() -> None:
    _logger.info('Запускаю задачу импорта АЗС ГПН')
    perform_controller_actions(
        controller_name="GPNController",
        func_name="import_azs"
    )
    _logger.info('Завершена задача импорта АЗС ГПН')


# async def update_group_limits_fn(orders: List[Dict[str, Any]]) -> None:
#     if not orders:
#         return None
#
#     sessionmanager = DatabaseSessionManager()
#     sessionmanager.init(PROD_URI)
#
#     async with sessionmanager.session() as session:
#         gpn_controller = GPNController(session)
#         await gpn_controller.init_system()
#         await gpn_controller.update_group_limits(orders=orders)
#
#     # Закрываем соединение с БД
#     await sessionmanager.close()
#
#
# @celery.task(name="GPN_UPDATE_GROUP_LIMITS")
# def gpn_update_group_limits(orders: List[Dict[str, Any]]) -> None:
#     asyncio.run(update_group_limits_fn(orders))

personal_account_str = str
delta_sum_float = float


@celery.task(name="GPN_UPDATE_GROUP_LIMITS")
def gpn_update_group_limits(gpn_group_limit_increase_deltas: Dict[personal_account_str, List[delta_sum_float]] = None,
                            gpn_group_limit_decrease_deltas: Dict[personal_account_str, List[delta_sum_float]] = None) \
        -> None:
    _logger.info('Запускаю задачу обновления групповых лимитов ГПН')
    perform_controller_actions(
        controller_name="GPNController",
        func_name="update_group_limits",
        gpn_group_limit_increase_deltas=gpn_group_limit_increase_deltas,
        gpn_group_limit_decrease_deltas=gpn_group_limit_decrease_deltas,
    )
    _logger.info('Завершена задача обновления групповых лимитов ГПН')


@celery.task(name="GPN_BINDING_CARDS")
def gpn_binding_cards(card_numbers: List[str], previous_company_id: str, new_company_id: str) -> None:
    _logger.info('Запускаю задачу привязки карт ГПН к организациям')
    perform_controller_actions(
        controller_name="GPNController",
        func_name="binding_cards",
        card_numbers=card_numbers,
        previous_company_id=previous_company_id,
        new_company_id=new_company_id
    )
    _logger.info('Завершена задачу привязки карт ГПН к организациям')


@celery.task(name="GPN_SYNC_CARD_STATES")
def gpn_sync_card_states() -> None:
    _logger.info('Начинаю синхронизацию состояний карт с ГПН')
    perform_controller_actions(
        controller_name="GPNController",
        func_name="sync_card_states"
    )
    _logger.info('Завершена синхронизация состояний карт с ГПН')


@celery.task(name="GPN_SYNC_GROUP_LIMITS")
def service_sync() -> None:
    _logger.info('Начинаю сервисную синхронизацию с ГПН для поиска и '
                 'исправления ошибок по картам, группам, лимитам')
    perform_controller_actions(
        controller_name="GPNController",
        func_name="sync_group_limits"
    )
    _logger.info('Завершена сервисная синхронизация с ГПН')


@celery.task(name="GPN_MAKE_GROUP_LIMITS_CHECK_REPORT")
def gpn_make_group_limits_check_report() -> None:
    _logger.info('Начинаю задачу формирования сверочного отчета по групповым лимитам ГПН')
    perform_controller_actions(
        controller_name="GPNController",
        func_name="make_group_limits_check_report"
    )
    _logger.info('Завершена задача формирования сверочного отчета по групповым лимитам ГПН')


@celery.task(name="GPN_TEST")
def gpn_test() -> None:
    api = GPNApi()
    regions = api.get_regions()
    print(regions)
    # api.set_card_group_limits([('5287241', 1500000)])
    # api.get_transactions(5)
    # product_types = api.get_product_types()
    # groups = api.get_card_groups()
    # for group in groups:
    #     if group['name'] == "5287241":
    #         limits = api.get_card_group_limits(group['id'])
    #         for limit in limits:
    #             print(limit)
    #         break
