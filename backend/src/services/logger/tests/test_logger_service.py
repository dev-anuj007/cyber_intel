"""Comprehensive Pytest Test Suite for Logger Service, Logfire Logger, Console Logger, Context, and Middleware."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.services.logger.context import (
    generate_trace_id,
    get_current_trace_id,
    get_journey_context,
    set_current_trace_id,
    update_journey_context,
)
from src.services.logger.internal.console_logger import ConsoleLogger
from src.services.logger.internal.logfire_logger import LogfireLogger
from src.services.logger.logger_service import LoggerService
from src.services.logger.middleware import UserJourneyMiddleware


def test_logger_context():
    set_current_trace_id("trace-abc-123")
    assert get_current_trace_id() == "trace-abc-123"

    update_journey_context(account_key="domain:test.com")
    ctx = get_journey_context()
    assert ctx.get("account_key") == "domain:test.com"

    tid = generate_trace_id()
    assert tid.startswith("trc_")


def test_console_logger():
    console = ConsoleLogger(service_name="test_service")
    console.info("Info message", key1="val1")
    console.warning("Warning message", alert=True)
    console.error("Error message", error="Some error")
    console.debug("Debug message")

    with console.span("test_span", custom_tag="tag"):
        pass


def test_logfire_logger():
    logfire = LogfireLogger(service_name="test_service")
    logfire.info("Info message logfire", k="v")
    logfire.warning("Warning message logfire")
    logfire.error("Error message logfire")
    logfire.debug("Debug message logfire")

    with logfire.span("logfire_span", item="x"):
        pass


def test_logger_service_facade():
    logger = LoggerService(service_name="facade_service")
    logger.info("Facade info", metric=100)
    logger.warning("Facade warn")
    logger.error("Facade error")
    logger.debug("Facade debug")

    with logger.span("facade_span", operation="query"):
        pass


def test_logging_middleware():
    test_app = FastAPI()
    test_app.add_middleware(UserJourneyMiddleware)

    @test_app.get("/ping")
    def ping():
        return {"ping": "pong"}

    client = TestClient(test_app)
    res = client.get("/ping")
    assert res.status_code == 200
    assert res.json() == {"ping": "pong"}
