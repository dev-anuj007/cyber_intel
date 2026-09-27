import sys
import time
import traceback
from contextlib import contextmanager
from typing import Any, Dict, Optional

from src.services.logger.internals.base_logger import BaseLogger


class ConsoleLogger(BaseLogger):
    def __init__(
        self,
        name: str = "app",
        extra: Optional[Dict[str, Any]] = None,
        json_format: Optional[bool] = None,
        service_name: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(name=name, extra=extra, service_name=service_name, **kwargs)
        self._json_format = json_format

    def _format(self, level: str, msg: str, **kwargs) -> str:
        return self.format_message(level, msg, json_format=self._json_format, **kwargs)

    def debug(self, msg: str, *args, **kwargs) -> None:
        print(self._format("DEBUG", msg, **kwargs), file=sys.stdout, flush=True)

    def info(self, msg: str, *args, **kwargs) -> None:
        print(self._format("INFO", msg, **kwargs), file=sys.stdout, flush=True)

    def warning(self, msg: str, *args, **kwargs) -> None:
        print(self._format("WARNING", msg, **kwargs), file=sys.stdout, flush=True)

    def error(self, msg: str, *args, **kwargs) -> None:
        print(self._format("ERROR", msg, **kwargs), file=sys.stderr, flush=True)

    def critical(self, msg: str, *args, **kwargs) -> None:
        print(self._format("CRITICAL", msg, **kwargs), file=sys.stderr, flush=True)

    def exception(self, msg: str, *args, **kwargs) -> None:
        kwargs["traceback"] = traceback.format_exc()
        print(self._format("EXCEPTION", msg, **kwargs), file=sys.stderr, flush=True)

    @contextmanager
    def span(self, name: str, **kwargs):
        start_time = time.perf_counter()
        self.info(f"==> [SPAN START] {name}", **kwargs)
        try:
            yield
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.info(f"<== [SPAN END] {name} (took {duration_ms:.2f}ms)", duration_ms=round(duration_ms, 2), **kwargs)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.error(
                f"<== [SPAN FAILED] {name} after {duration_ms:.2f}ms: {exc}",
                duration_ms=round(duration_ms, 2),
                error=str(exc),
                **kwargs,
            )
            raise

    def bind(self, **kwargs) -> "ConsoleLogger":
        merged = self.extra.copy()
        merged.update(kwargs)
        return ConsoleLogger(name=self.name, extra=merged, json_format=self._json_format)
