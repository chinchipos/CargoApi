import traceback

from src.utils.log import ColoredLogger

khnp_connector_logger = ColoredLogger(logfile_name='schedule.log', logger_name='KHNPConnector')
khnp_parser_logger = ColoredLogger(logfile_name='schedule.log', logger_name='KHNPParser')


class KHNPConnectorError(Exception):

    def __init__(self, trace: bool, message: str) -> None:
        if trace:
            trace_info = traceback.format_exc()
            khnp_connector_logger.error(message)
            khnp_connector_logger.error(trace_info)

        else:
            khnp_connector_logger.error(message)

        super().__init__(message)


class KHNPParserError(Exception):

    def __init__(self, trace: bool, message: str) -> None:
        if trace:
            trace_info = traceback.format_exc()
            khnp_parser_logger.error(message)
            khnp_parser_logger.error(trace_info)

        else:
            khnp_parser_logger.error(message)

        super().__init__(message)
