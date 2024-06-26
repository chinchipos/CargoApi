import logging
import os
from logging.handlers import RotatingFileHandler

from termcolor import colored

from src.config import LOG_DIR


class ColoredLogger:

    def __init__(self, logfile_name: str, logger_name: str):
        logfile_path = os.path.join(LOG_DIR, logfile_name)
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)

        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.INFO)

        formatter = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s", '%Y-%m-%d %H:%M:%S')

        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        handler = RotatingFileHandler(filename=logfile_path, maxBytes=1048576, backupCount=3)
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def info(self, message: str) -> None:
        self.logger.info(message)

    def warning(self, message: str) -> None:
        self.logger.warning(colored(message, 'light_yellow'))

    def error(self, message: str) -> None:
        self.logger.error(colored(message, 'light_red'))


logger = ColoredLogger(logfile_name='api.log', logger_name='CARGONOMICA-API')
