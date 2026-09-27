from datetime import datetime, timezone
from typing import Any, Dict, List, Sequence

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.core.exceptions import AppException
from src.services.logger.context import get_current_trace_id
from src.services.logger.logger_service import get_logger

logger = get_logger("error_boundary")


def build_error_payload(
    code: str,
    message: str,
    status_code: int,
    details: Any = None,
    trace_id: Any = None,
) -> Dict[str, Any]:
    active_trace_id = trace_id or get_current_trace_id()
    return {
        "success": False if False else False,
        "detail": message,
        "error": {
            "code": code,
            "message": message,
            "status_code": status_code,
            "details": details,
            "trace_id": active_trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }


def format_validation_errors(errors: Sequence[Any]) -> List[Dict[str, Any]]:
    formatted = []
    for err in errors:
        if isinstance(err, dict):
            loc = err.get("loc", [])
            field = ".".join(str(p) for p in loc if p != "body") or "body"
            msg = err.get("msg", "Invalid value")
            err_type = err.get("type", "value_error")
            formatted.append(
                {
                    "field": field,
                    "message": msg,
                    "type": err_type,
                }
            )
    return formatted


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        trace_id = get_current_trace_id()
        if exc.status_code >= 500:
            logger.error(
                f"Domain exception {exc.code}: {exc.message}",
                error_code=exc.code,
                status_code=exc.status_code,
                path=request.url.path,
                details=exc.details,
            )
        else:
            logger.warning(
                f"Client error {exc.code}: {exc.message}",
                error_code=exc.code,
                status_code=exc.status_code,
                path=request.url.path,
                details=exc.details,
            )

        payload = build_error_payload(
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
            trace_id=trace_id,
        )
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        trace_id = get_current_trace_id()
        details = format_validation_errors(exc.errors())
        error_count = len(details)
        msg = f"Input validation failed on {error_count} field{'s' if error_count != 1 else ''}"

        logger.warning(
            f"Validation error on {request.url.path}: {msg}",
            path=request.url.path,
            details=details,
        )

        payload = build_error_payload(
            code="VALIDATION_ERROR",
            message=msg,
            status_code=422,
            details=details,
            trace_id=trace_id,
        )
        return JSONResponse(status_code=422, content=payload)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        trace_id = get_current_trace_id()
        code_map = {
            400: "BAD_REQUEST",
            401: "UNAUTHENTICATED",
            403: "PERMISSION_DENIED",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            409: "CONFLICT",
            422: "UNPROCESSABLE_ENTITY",
            429: "RATE_LIMIT_EXCEEDED",
            500: "INTERNAL_SERVER_ERROR",
            502: "BAD_GATEWAY",
            503: "SERVICE_UNAVAILABLE",
        }
        code = code_map.get(exc.status_code, f"HTTP_{exc.status_code}")
        message = str(exc.detail) if exc.detail else "An HTTP error occurred"

        if exc.status_code >= 500:
            logger.error(
                f"HTTP {exc.status_code} on {request.url.path}: {message}",
                status_code=exc.status_code,
                path=request.url.path,
            )
        else:
            logger.warning(
                f"HTTP {exc.status_code} on {request.url.path}: {message}",
                status_code=exc.status_code,
                path=request.url.path,
            )

        payload = build_error_payload(
            code=code,
            message=message,
            status_code=exc.status_code,
            trace_id=trace_id,
        )
        return JSONResponse(status_code=exc.status_code, content=payload, headers=getattr(exc, "headers", None))

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        trace_id = get_current_trace_id()
        logger.exception(
            f"Unhandled server exception on {request.url.path}: {exc}",
            path=request.url.path,
            error=str(exc),
        )

        payload = build_error_payload(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected internal server error occurred. Please quote the trace ID for support.",
            status_code=500,
            trace_id=trace_id,
        )
        return JSONResponse(status_code=500, content=payload)
