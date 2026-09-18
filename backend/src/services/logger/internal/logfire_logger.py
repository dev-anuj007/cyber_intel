import time
import traceback
from contextlib import contextmanager
from typing import Any, Dict, Optional

try:
    import logfire
    _LOGFIRE_AVAILABLE = True
except ImportError:
    _LOGFIRE_AVAILABLE = False
    logfire = None

from src.core.config import LOGFIRE_TOKEN, SERVICE_NAME, ENVIRONMENT
from src.services.logger.internal.base_logger import BaseLogger
from src.services.logger.context import get_current_trace_id

_LOGFIRE_INITIALIZED = False


def init_logfire_client(token: Optional[str] = None, service_name: Optional[str] = None) -> bool:
    global _LOGFIRE_INITIALIZED

    if _LOGFIRE_INITIALIZED:
        return True

    if not _LOGFIRE_AVAILABLE:
        return False

    auth_token = token or LOGFIRE_TOKEN
    svc_name = service_name or SERVICE_NAME or "sales-intel-api"

    try:
        if auth_token:
            logfire.configure(
                token=auth_token,
                service_name=svc_name,
                environment=ENVIRONMENT or "production",
                send_to_logfire=True,
                inspect_arguments=False,
            )
        else:
            logfire.configure(
                service_name=svc_name,
                environment=ENVIRONMENT or "production",
                inspect_arguments=False,
            )
        _LOGFIRE_INITIALIZED = True
        return True
    except Exception as e:
        print(f"[LogfireLogger] Warning: Failed to initialize Logfire: {e}")
        return False


class LogfireLogger(BaseLogger):
    def __init__(self, name: str = "app", extra: Optional[Dict[str, Any]] = None):
        super().__init__(name=name, extra=extra)
        if not _LOGFIRE_INITIALIZED:
            init_logfire_client()

    def _prepare_attributes(self, **kwargs) -> Dict[str, Any]:
        attrs = self.get_context()
        attrs.update(kwargs)
        attrs["logger_name"] = self.name
        trace_id = get_current_trace_id()
        if trace_id:
            attrs["trace_id"] = trace_id
        return attrs

    def debug(self, msg: str, *args, **kwargs) -> None:
        attrs = self._prepare_attributes(**kwargs)
        if _LOGFIRE_AVAILABLE and logfire:
            logfire.debug(f"[{self.name}] {msg}", **attrs)
        else:
            print(self.format_message("DEBUG", msg, **attrs))

    def info(self, msg: str, *args, **kwargs) -> None:
        attrs = self._prepare_attributes(**kwargs)
        if _LOGFIRE_AVAILABLE and logfire:
            logfire.info(f"[{self.name}] {msg}", **attrs)
        else:
            print(self.format_message("INFO", msg, **attrs))

    def warning(self, msg: str, *args, **kwargs) -> None:
        attrs = self._prepare_attributes(**kwargs)
        if _LOGFIRE_AVAILABLE and logfire:
            logfire.warn(f"[{self.name}] {msg}", **attrs)
        else:
            print(self.format_message("WARNING", msg, **attrs))

    def error(self, msg: str, *args, **kwargs) -> None:
        attrs = self._prepare_attributes(**kwargs)
        if _LOGFIRE_AVAILABLE and logfire:
            logfire.error(f"[{self.name}] {msg}", **attrs)
        else:
            print(self.format_message("ERROR", msg, **attrs))

    def critical(self, msg: str, *args, **kwargs) -> None:
        attrs = self._prepare_attributes(**kwargs)
        if _LOGFIRE_AVAILABLE and logfire:
            logfire.fatal(f"[{self.name}] {msg}", **attrs)
        else:
            print(self.format_message("CRITICAL", msg, **attrs))

    def exception(self, msg: str, *args, **kwargs) -> None:
        attrs = self._prepare_attributes(**kwargs)
        if _LOGFIRE_AVAILABLE and logfire:
            logfire.exception(f"[{self.name}] {msg}", **attrs)
        else:
            attrs["traceback"] = traceback.format_exc()
            print(self.format_message("EXCEPTION", msg, **attrs))

    @contextmanager
    def span(self, name: str, **kwargs):
        attrs = self._prepare_attributes(**kwargs)
        span_title = f"{self.name}.{name}"
        
        if _LOGFIRE_AVAILABLE and logfire:
            with logfire.span(span_title, **attrs):
                yield
        else:
            start_time = time.perf_counter()
            self.info(f"==> [SPAN START] {span_title}", **attrs)
            try:
                yield
                dur = (time.perf_counter() - start_time) * 1000
                self.info(f"<== [SPAN END] {span_title} ({dur:.2f}ms)", duration_ms=round(dur, 2), **attrs)
            except Exception as e:
                dur = (time.perf_counter() - start_time) * 1000
                self.error(f"<== [SPAN FAILED] {span_title} after {dur:.2f}ms: {e}", duration_ms=round(dur, 2), error=str(e), **attrs)
                raise

    def bind(self, **kwargs) -> "LogfireLogger":
        merged = self.extra.copy()
        merged.update(kwargs)
        return LogfireLogger(name=self.name, extra=merged)
