import queue
import threading
import time
import traceback
from contextlib import contextmanager
from typing import Any, Callable, Dict, Optional

try:
    import logfire

    _LOGFIRE_AVAILABLE = True
except ImportError:
    _LOGFIRE_AVAILABLE = False
    logfire = None

from src.core.config import ENVIRONMENT, LOGFIRE_TOKEN, SERVICE_NAME
from src.services.logger.context import get_current_trace_id
from src.services.logger.internal.base_logger import BaseLogger

_LOGFIRE_INITIALIZED = False

# Dedicated asynchronous background log queue & daemon worker
_LOG_QUEUE: queue.Queue = queue.Queue(maxsize=10000)
_WORKER_THREAD: Optional[threading.Thread] = None
_WORKER_LOCK = threading.Lock()


def _async_worker_loop():
    """Background consumer daemon executing logfire transmissions asynchronously."""
    while True:
        try:
            item = _LOG_QUEUE.get()
            if item is None:
                break
            fn, args, kwargs = item
            fn(*args, **kwargs)
            _LOG_QUEUE.task_done()
        except Exception:
            pass


def _ensure_worker_running():
    global _WORKER_THREAD
    if _WORKER_THREAD is None or not _WORKER_THREAD.is_alive():
        with _WORKER_LOCK:
            if _WORKER_THREAD is None or not _WORKER_THREAD.is_alive():
                t = threading.Thread(
                    target=_async_worker_loop,
                    name="LogfireAsyncWorker",
                    daemon=True,
                )
                t.start()
                _WORKER_THREAD = t


def _dispatch_async(fn: Callable, *args, **kwargs):
    """Enqueue logging task to background worker for zero-overhead execution."""
    _ensure_worker_running()
    try:
        _LOG_QUEUE.put_nowait((fn, args, kwargs))
    except queue.Full:
        pass


def init_logfire_client(token: Optional[str] = None, service_name: Optional[str] = None) -> bool:
    global _LOGFIRE_INITIALIZED

    if _LOGFIRE_INITIALIZED:
        return True

    if not _LOGFIRE_AVAILABLE or not logfire:
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
        _ensure_worker_running()
        return True
    except Exception as e:
        print(f"[LogfireLogger] Warning: Failed to initialize Logfire: {e}")
        return False


class LogfireLogger(BaseLogger):
    def __init__(
        self,
        name: str = "app",
        extra: Optional[Dict[str, Any]] = None,
        service_name: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(name=name, extra=extra, service_name=service_name, **kwargs)
        if not _LOGFIRE_INITIALIZED:
            init_logfire_client(service_name=service_name or name)

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
        if _LOGFIRE_AVAILABLE and logfire and _LOGFIRE_INITIALIZED:
            _dispatch_async(logfire.debug, f"[{self.name}] {msg}", **attrs)
        else:
            print(self.format_message("DEBUG", msg, **attrs))

    def info(self, msg: str, *args, **kwargs) -> None:
        attrs = self._prepare_attributes(**kwargs)
        if _LOGFIRE_AVAILABLE and logfire and _LOGFIRE_INITIALIZED:
            _dispatch_async(logfire.info, f"[{self.name}] {msg}", **attrs)
        else:
            print(self.format_message("INFO", msg, **attrs))

    def warning(self, msg: str, *args, **kwargs) -> None:
        attrs = self._prepare_attributes(**kwargs)
        if _LOGFIRE_AVAILABLE and logfire and _LOGFIRE_INITIALIZED:
            _dispatch_async(logfire.warn, f"[{self.name}] {msg}", **attrs)
        else:
            print(self.format_message("WARNING", msg, **attrs))

    def error(self, msg: str, *args, **kwargs) -> None:
        attrs = self._prepare_attributes(**kwargs)
        if _LOGFIRE_AVAILABLE and logfire and _LOGFIRE_INITIALIZED:
            _dispatch_async(logfire.error, f"[{self.name}] {msg}", **attrs)
        else:
            print(self.format_message("ERROR", msg, **attrs))

    def critical(self, msg: str, *args, **kwargs) -> None:
        attrs = self._prepare_attributes(**kwargs)
        if _LOGFIRE_AVAILABLE and logfire and _LOGFIRE_INITIALIZED:
            _dispatch_async(logfire.fatal, f"[{self.name}] {msg}", **attrs)
        else:
            print(self.format_message("CRITICAL", msg, **attrs))

    def exception(self, msg: str, *args, **kwargs) -> None:
        attrs = self._prepare_attributes(**kwargs)
        if _LOGFIRE_AVAILABLE and logfire and _LOGFIRE_INITIALIZED:
            _dispatch_async(logfire.exception, f"[{self.name}] {msg}", **attrs)
        else:
            attrs["traceback"] = traceback.format_exc()
            print(self.format_message("EXCEPTION", msg, **attrs))

    @contextmanager
    def span(self, name: str, **kwargs):
        attrs = self._prepare_attributes(**kwargs)
        span_title = f"{self.name}.{name}"
        start_time = time.perf_counter()

        try:
            yield
            dur = (time.perf_counter() - start_time) * 1000
            attrs["duration_ms"] = round(dur, 2)
            if _LOGFIRE_AVAILABLE and logfire and _LOGFIRE_INITIALIZED:
                _dispatch_async(logfire.info, f"[{span_title}] completed in {dur:.2f}ms", **attrs)
        except Exception as e:
            dur = (time.perf_counter() - start_time) * 1000
            attrs["duration_ms"] = round(dur, 2)
            attrs["error"] = str(e)
            if _LOGFIRE_AVAILABLE and logfire and _LOGFIRE_INITIALIZED:
                _dispatch_async(logfire.error, f"[{span_title}] failed after {dur:.2f}ms: {e}", **attrs)
            raise

    def bind(self, **kwargs) -> "LogfireLogger":
        merged = self.extra.copy()
        merged.update(kwargs)
        return LogfireLogger(name=self.name, extra=merged)
