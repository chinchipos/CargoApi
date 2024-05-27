import traceback

from src.utils.log import ColoredLogger

sync_logger = ColoredLogger(logfile_name='khnp.log', logger_name='KHNP')


class BaseError(Exception):

    def __init__(self, trace: bool, message: str) -> None:
        if trace:
            trace_info = traceback.format_exc()
            sync_logger.error(message)
            sync_logger.error(trace_info)

        else:
            sync_logger.error(message)

        super().__init__(message)


class SyncError(BaseError):
    ...
