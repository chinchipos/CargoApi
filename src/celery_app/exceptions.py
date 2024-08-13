from src.utils.loggers import get_logger

_logger = get_logger(name="CELERY", filename="celery.log")


class CeleryError(Exception):

    def __init__(self, message: str, trace: bool = True) -> None:
        if trace:
            _logger.exception(message)

        else:
            _logger.error(message)

        super().__init__(message)
