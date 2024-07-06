import traceback

from src.utils.log import ColoredLogger

sber_api_logger = ColoredLogger(logfile_name='schedule.log', logger_name='SberApi')
sber_connector_logger = ColoredLogger(logfile_name='schedule.log', logger_name='SberConnector')


class SberApiError(Exception):

    def __init__(self, message: str, trace: bool = True) -> None:
        if trace:
            trace_info = traceback.format_exc()
            sber_api_logger.error(message)
            sber_api_logger.error(trace_info)

        else:
            sber_api_logger.error(message)

        super().__init__(message)


class SberConnectorError(Exception):

    def __init__(self, message: str, trace: bool = True) -> None:
        if trace:
            trace_info = traceback.format_exc()
            sber_connector_logger.error(message)
            sber_connector_logger.error(trace_info)

        else:
            sber_connector_logger.error(message)

        super().__init__(message)
