from pathlib import Path
from typing import Any, Optional, Union

from src.services.database.internals.connection import DatabaseSessionManager
from src.services.database.internals.repositories.reader import DatabaseReader
from src.services.database.internals.repositories.writer import DatabaseWriter
from src.services.database.protocols import (
    IDatabaseReader,
    IDatabaseService,
    IDatabaseSessionManager,
    IDatabaseWriter,
)
from src.services.database.types import DatabaseConfig


class DatabaseServiceDependencyContext:
    def __init__(
        self,
        session_manager: IDatabaseSessionManager,
        reader: IDatabaseReader,
        writer: IDatabaseWriter,
    ):
        self.session_manager = session_manager
        self.reader = reader
        self.writer = writer


def get_database_dependency_context(
    db_path: Optional[Union[Path, str]] = None,
    database_url: Optional[str] = None,
) -> DatabaseServiceDependencyContext:
    config = DatabaseConfig(db_path=db_path, database_url=database_url)
    session_manager = DatabaseSessionManager(config=config)
    reader = DatabaseReader(session_manager=session_manager)
    writer = DatabaseWriter(session_manager=session_manager)
    return DatabaseServiceDependencyContext(
        session_manager=session_manager,
        reader=reader,
        writer=writer,
    )


def create_database_service(
    context: Optional[DatabaseServiceDependencyContext] = None,
    db_path: Optional[Union[Path, str]] = None,
    database_url: Optional[str] = None,
) -> IDatabaseService:
    from src.services.database.database_service import DatabaseService

    if context is None:
        context = get_database_dependency_context(db_path=db_path, database_url=database_url)
    return DatabaseService(context=context)


default_database_service = create_database_service()


def get_database_service() -> IDatabaseService:
    return default_database_service


get_db_service = get_database_service


def is_deployed() -> bool:
    import os

    return bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME") or os.getenv("STAGE") == "prod" or os.getenv("LAMBDA_TASK_ROOT"))


def get_db_connection():
    from contextlib import contextmanager

    @contextmanager
    def _conn_ctx():
        with default_database_service.get_connection() as conn:
            yield conn

    return _conn_ctx()


def get_db_session(conn: Optional[Any] = None):
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
    default_database_service.init_schema()
