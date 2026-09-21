"""Database service module.

All production/staging paths use the global ``default_database_service``
which is backed by PostgreSQL (DATABASE_URL env var).

The ``db_path`` parameter on ``DatabaseService.__init__`` is preserved for
test isolation only — tests instantiate their own ``DatabaseService(db_path=...)``
directly and never go through these module-level helpers with a path argument.
"""

import os
from contextlib import contextmanager
from typing import Any, Optional

from src.services.database.api import get_db_service
from src.services.database.api import router as database_router
from src.services.database.database_service import DatabaseService
from src.services.database.types import (
    DatabaseHealth,
    DatabaseStats,
    IDatabaseService,
    QueryRequest,
    QueryResponse,
)

default_database_service = DatabaseService()


def is_deployed() -> bool:
    """Returns True if running in AWS Lambda / Cloud environment."""
    return bool(
        os.getenv("AWS_LAMBDA_FUNCTION_NAME")
        or os.getenv("STAGE") == "prod"
        or os.getenv("LAMBDA_TASK_ROOT")
    )


@contextmanager
def get_db_connection():
    """Yield a raw PostgreSQL connection from the default service pool."""
    with default_database_service.get_connection() as conn:
        yield conn


def get_db_session(conn: Optional[Any] = None):
    """Return a SQLModel Session.

    If ``conn`` is a raw SQLite connection (test isolation), wrap it directly.
    Otherwise use the default PostgreSQL-backed service.
    """
    import sqlite3
    from sqlmodel import create_engine

    if conn is not None:
        raw = conn
        if hasattr(raw, "_conn"):
            raw = raw._conn
        if hasattr(raw, "raw_connection"):
            raw = raw.raw_connection
        if isinstance(raw, sqlite3.Connection):
            from sqlmodel import Session
            engine = create_engine("sqlite://", creator=lambda: raw)
            return Session(engine)

    return default_database_service.get_session(conn)


def init_database() -> None:
    """Initialize schema on the default PostgreSQL database."""
    default_database_service.init_schema()


__all__ = [
    "IDatabaseService",
    "DatabaseHealth",
    "DatabaseStats",
    "QueryRequest",
    "QueryResponse",
    "DatabaseService",
    "default_database_service",
    "database_router",
    "get_db_service",
    "get_db_connection",
    "get_db_session",
    "init_database",
    "is_deployed",
]
