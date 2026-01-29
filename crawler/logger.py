"""Custom logger with colored console output and file logging."""

import logging

from colorama import Fore, Style, init

import config

init(autoreset=True)


class Logger:
    """Custom logger with colored console output and file logging."""

    def __init__(self, log_file: str = config.LOG_FILE):
        self.logger = logging.getLogger("ContactFormCrawler")
        self.logger.setLevel(getattr(logging, config.LOG_LEVEL))

        # File handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

        # Console handler (we'll handle formatting ourselves for colors)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, config.LOG_LEVEL))
        console_handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(console_handler)

    def info(self, msg: str):
        self.logger.info(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} {msg}")

    def success(self, msg: str):
        self.logger.info(f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} {msg}")

    def warning(self, msg: str):
        self.logger.warning(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} {msg}")

    def error(self, msg: str):
        self.logger.error(f"{Fore.RED}[ERROR]{Style.RESET_ALL} {msg}")

    def debug(self, msg: str):
        self.logger.debug(f"{Fore.MAGENTA}[DEBUG]{Style.RESET_ALL} {msg}")
