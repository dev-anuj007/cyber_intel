from src.services.logger.internals.base_logger import BaseLogger
from src.services.logger.logger_service import LoggerService, default_logger_service



def get_logger_service() -> LoggerService:
    return default_logger_service


def get_app_logger(name: str = "app") -> BaseLogger:
    return default_logger_service.get_logger(name)
