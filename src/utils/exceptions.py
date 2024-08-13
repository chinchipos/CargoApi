import traceback

from src.utils.loggers import ColoredLogger


class BadRequestException(Exception):
    def __init__(self, message: str):
        self.message = message


class ForbiddenException(Exception):
    def __init__(self):
        self.message = 'Отсутствуют необходимые права доступа'


class DBException(Exception):
    def __init__(self):
        self.message = 'Ошибка при выполнении запроса к БД API'


class DBDuplicateException(Exception):
    def __init__(self):
        self.message = 'Нарушение целостности: попытка добавить идентичную запись.'


api_logger = ColoredLogger(logfile_name='api.log', logger_name='API')


class ApiError(Exception):

    def __init__(self, message: str, trace: bool = True) -> None:
        if trace:
            trace_info = traceback.format_exc()
            self.message = message
            api_logger.error(message)
            api_logger.error(trace_info)

        else:
            api_logger.error(message)

        super().__init__(message)
