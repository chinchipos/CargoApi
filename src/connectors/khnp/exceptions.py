import traceback

from src.utils.log import ColoredLogger


khnp_logger = ColoredLogger(logfile_name='khnp.log', logger_name='KHNP')


class BaseError(Exception):

    def __init__(self, trace: bool, message: str) -> None:
        if trace:
            trace_info = traceback.format_exc()
            khnp_logger.error(message)
            khnp_logger.error(trace_info)

        else:
            khnp_logger.error(message)

        super().__init__(message)


class KHNPConnectorError(BaseError):
    ...


class KHNPParserError(BaseError):
    ...
