"""Logger Service Factory & Resolver."""

from typing import Dict, Optional

from src.core.config import ENVIRONMENT, LOGFIRE_TOKEN
from src.services.logger.internals.base_logger import BaseLogger
from src.services.logger.internals.console_logger import ConsoleLogger
from src.services.logger.internals.logfire_logger import LogfireLogger



class LoggerService:
    LOCAL_ENVIRONMENTS = {"local", "dev", "development", "test"}

    def __init__(
        self,
        env: Optional[str] = None,
        service_name: Optional[str] = None,
        name: Optional[str] = None,
        **kwargs,
    ):
        self._env = (env or ENVIRONMENT or "local").lower()
        self._service_name = service_name or name or "app"
        self._instances: Dict[str, BaseLogger] = {}

    @property
    def is_local(self) -> bool:
        return self._env in self.LOCAL_ENVIRONMENTS

    def get_logger(self, name: Optional[str] = None) -> BaseLogger:
        target_name = name or self._service_name or "app"
        if target_name in self._instances:
            return self._instances[target_name]

        if LOGFIRE_TOKEN:
            logger = LogfireLogger(name=target_name)
        elif self.is_local:
            logger = ConsoleLogger(name=target_name)
        else:
            logger = ConsoleLogger(name=target_name)
            logger.warning(
                f"Deployed mode '{self._env}' detected but LOGFIRE_TOKEN is missing. Defaulting to ConsoleLogger."
            )

        self._instances[target_name] = logger
        return logger

    def debug(self, msg: str, *args, **kwargs) -> None:
        self.get_logger().debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:
        self.get_logger().info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        self.get_logger().warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        self.get_logger().error(msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs) -> None:
        self.get_logger().critical(msg, *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs) -> None:
        self.get_logger().exception(msg, *args, **kwargs)

    def span(self, name: str, **kwargs):
        return self.get_logger().span(name, **kwargs)

    def set_environment(self, env: str) -> None:
        self._env = env.lower()
        self._instances.clear()


default_logger_service = LoggerService()


def get_logger(name: str = "app") -> BaseLogger:
    return default_logger_service.get_logger(name)


def span(name: str, **kwargs):
    return default_logger_service.get_logger().span(name, **kwargs)
