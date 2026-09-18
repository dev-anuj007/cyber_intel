import json
import os
from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.services.logger.context import (
    get_current_trace_id,
    set_current_trace_id,
    get_journey_context,
)


class BaseLogger(ABC):
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"

    LEVEL_COLORS = {
        "DEBUG": DIM + CYAN,
        "INFO": GREEN,
        "WARNING": YELLOW,
        "ERROR": RED,
        "CRITICAL": BOLD + RED,
        "EXCEPTION": BOLD + RED,
    }

    def __init__(self, name: str = "app", extra: Optional[Dict[str, Any]] = None):
        self.name = name
        self.extra = extra or {}

    @abstractmethod
    def debug(self, msg: str, *args, **kwargs) -> None:
        pass

    @abstractmethod
    def info(self, msg: str, *args, **kwargs) -> None:
        pass

    @abstractmethod
    def warning(self, msg: str, *args, **kwargs) -> None:
        pass

    @abstractmethod
    def error(self, msg: str, *args, **kwargs) -> None:
        pass

    @abstractmethod
    def critical(self, msg: str, *args, **kwargs) -> None:
        pass

    @abstractmethod
    def exception(self, msg: str, *args, **kwargs) -> None:
        pass

    @abstractmethod
    def span(self, name: str, **kwargs) -> AbstractContextManager:
        pass

    @abstractmethod
    def bind(self, **kwargs) -> "BaseLogger":
        pass

    def get_trace_id(self) -> Optional[str]:
        return get_current_trace_id()

    def set_trace_id(self, trace_id: str) -> None:
        set_current_trace_id(trace_id)

    def get_context(self) -> Dict[str, Any]:
        ctx = get_journey_context()
        ctx.update(self.extra)
        trace_id = self.get_trace_id()
        if trace_id:
            ctx["trace_id"] = trace_id
        return ctx

    def build_structured_record(self, level: str, msg: str, **kwargs) -> Dict[str, Any]:
        ctx = self.get_context()
        ctx.update(kwargs)
        trace_id = ctx.pop("trace_id", self.get_trace_id())

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level.upper(),
            "logger": self.name,
            "trace_id": trace_id,
            "message": msg,
            "attributes": ctx,
        }

    def format_message(self, level: str, msg: str, json_format: Optional[bool] = None, **kwargs) -> str:
        use_json = (
            json_format
            if json_format is not None
            else os.getenv("LOG_FORMAT", "text").lower() == "json"
        )
        record = self.build_structured_record(level, msg, **kwargs)

        if use_json:
            return json.dumps(record, default=str)

        timestamp = record["timestamp"].replace("T", " ")[:23]
        color = self.LEVEL_COLORS.get(level.upper(), self.RESET)
        trace_id = record["trace_id"] or "-"
        attrs = record["attributes"]

        extra_str = ""
        if attrs:
            try:
                extra_str = f" {self.DIM}| {json.dumps(attrs, default=str)}{self.RESET}"
            except Exception:
                extra_str = f" {self.DIM}| {str(attrs)}{self.RESET}"

        return f"{self.DIM}{timestamp}{self.RESET} {color}[{level.upper():<5}]{self.RESET} {self.MAGENTA}[Trace:{trace_id}]{self.RESET} {self.BLUE}{self.name}:{self.RESET} {msg}{extra_str}"
