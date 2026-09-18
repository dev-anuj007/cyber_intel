"""Logger Service Factory & Resolver."""

import os
from typing import Dict, Optional

from src.core.config import ENVIRONMENT, LOGFIRE_TOKEN
from src.services.logger.internal.base_logger import BaseLogger
from src.services.logger.internal.console_logger import ConsoleLogger
from src.services.logger.internal.logfire_logger import LogfireLogger


class LoggerService:
    LOCAL_ENVIRONMENTS = {"local", "dev", "development", "test"}

    def __init__(self, env: Optional[str] = None):
        self._env = (env or ENVIRONMENT or "local").lower()
        self._instances: Dict[str, BaseLogger] = {}

    @property
    def is_local(self) -> bool:
        return self._env in self.LOCAL_ENVIRONMENTS

    def get_logger(self, name: str = "app") -> BaseLogger:
        if name in self._instances:
            return self._instances[name]

        if self.is_local:
            logger = ConsoleLogger(name=name)
        else:
            if LOGFIRE_TOKEN:
                logger = LogfireLogger(name=name)
            else:
                logger = ConsoleLogger(name=name)
                logger.warning(
                    f"Deployed mode '{self._env}' detected but LOGFIRE_TOKEN is missing. Defaulting to ConsoleLogger."
                )

        self._instances[name] = logger
        return logger

    def set_environment(self, env: str) -> None:
        self._env = env.lower()
        self._instances.clear()


default_logger_service = LoggerService()


def get_logger(name: str = "app") -> BaseLogger:
    return default_logger_service.get_logger(name)


def span(name: str, **kwargs):
    return default_logger_service.get_logger().span(name, **kwargs)

