import traceback

from src.utils.log import ColoredLogger

celery_logger = ColoredLogger(logfile_name='schedule.log', logger_name='Celery')


class CeleryError(Exception):

    def __init__(self, trace: bool = True, message: str = "") -> None:
        if trace:
            trace_info = traceback.format_exc()
            celery_logger.error(message)
            celery_logger.error(trace_info)

        else:
            celery_logger.error(message)

        super().__init__(message)