"""Logger Service Module.

Provides abstracted logging interfaces, runtime resolver for Console vs Logfire logging,
and unified distributed trace ID tracking across full user journeys.
"""

from src.services.logger.internal.base_logger import BaseLogger
from src.services.logger.internal.console_logger import ConsoleLogger
from src.services.logger.internal.logfire_logger import LogfireLogger
from src.services.logger.logger_service import LoggerService, default_logger_service, get_logger, span
from src.services.logger.context import (
    generate_trace_id,
    get_current_trace_id,
    set_current_trace_id,
    get_journey_context,
    update_journey_context,
)
from src.services.logger.middleware import UserJourneyMiddleware

__all__ = [
    "BaseLogger",
    "ConsoleLogger",
    "LogfireLogger",
    "LoggerService",
    "default_logger_service",
    "get_logger",
    "span",
    "generate_trace_id",
    "get_current_trace_id",
    "set_current_trace_id",
    "get_journey_context",
    "update_journey_context",
    "UserJourneyMiddleware",
]

