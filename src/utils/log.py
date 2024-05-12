import logging
import os
from logging.handlers import RotatingFileHandler

from termcolor import colored


class ColoredLogger:

    def __init__(self):
        logfile_dir = os.path.join(os.getcwd(), 'log')
        logfile_path = os.path.join(logfile_dir, 'api.log')
        if not os.path.exists(logfile_dir):
            os.makedirs(logfile_dir)

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[
                RotatingFileHandler(filename=logfile_path, maxBytes=1048576, backupCount=3),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('CARGONOMICA-API')

    def info(self, message: str) -> None:
        self.logger.info(message)

    def warning(self, message: str) -> None:
        self.logger.warning(colored(message, 'light_yellow'))

    def error(self, message: str) -> None:
        self.logger.error(colored(message, 'light_red'))


logger = ColoredLogger()
