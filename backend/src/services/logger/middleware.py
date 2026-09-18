import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.services.logger.context import (
    generate_trace_id,
    set_current_trace_id,
    reset_trace_id,
    set_journey_context,
    reset_journey_context,
)
from src.services.logger.logger_service import get_logger


class UserJourneyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, logger_name: str = "http.journey"):
        super().__init__(app)
        self.logger = get_logger(logger_name)

    async def dispatch(self, request: Request, call_next) -> Response:
        incoming_trace_id = (
            request.headers.get("x-trace-id")
            or request.headers.get("x-request-id")
            or request.headers.get("traceparent")
        )
        trace_id = incoming_trace_id or generate_trace_id()

        trace_token = set_current_trace_id(trace_id)
        
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        path = request.url.path
        method = request.method
        query_params = str(request.query_params) if request.query_params else None

        journey_data = {
            "method": method,
            "path": path,
            "client_ip": client_ip,
            "user_agent": user_agent,
            "query_params": query_params,
        }
        journey_token = set_journey_context(journey_data)

        start_time = time.perf_counter()

        self.logger.info(
            f"[JOURNEY START] {method} {path}",
            **journey_data,
        )

        try:
            with self.logger.span(f"request:{method}_{path}"):
                response = await call_next(request)

            duration_ms = (time.perf_counter() - start_time) * 1000

            response.headers["X-Trace-Id"] = trace_id
            response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"

            self.logger.info(
                f"[JOURNEY COMPLETE] {method} {path} -> {response.status_code} ({duration_ms:.2f}ms)",
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )

            return response

        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.logger.exception(
                f"[JOURNEY FAILED] {method} {path} after {duration_ms:.2f}ms: {exc}",
                duration_ms=round(duration_ms, 2),
                error=str(exc),
            )
            raise

        finally:
            reset_trace_id(trace_token)
            reset_journey_context(journey_token)
