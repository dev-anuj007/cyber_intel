from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from sqlmodel import Session

from src.services.database.internals.connection import DatabaseSessionManager
from src.services.database.internals.repositories.reader import DatabaseReader
from src.services.database.internals.repositories.writer import DatabaseWriter
from src.services.database.protocols import (
    IDatabaseConnectionContext,
    IDatabaseReader,
    IDatabaseService,
    IDatabaseSessionManager,
    IDatabaseWriter,
)
from src.services.database.types import (
    DatabaseConfig,
    DatabaseHealth,
    DatabaseStats,
)


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
        context = get_database_dependency_context(
            db_path=db_path, database_url=database_url
        )
    return DatabaseService(context=context)


_default_database_service: Optional[IDatabaseService] = None


def get_database_service() -> IDatabaseService:
    global _default_database_service
    if _default_database_service is None:
        _default_database_service = create_database_service()
    return _default_database_service


get_db_service = get_database_service


class _LazyDatabaseServiceProxy(IDatabaseService):
    @property
    def is_postgres(self) -> bool:
        return get_database_service().is_postgres

    def get_connection(self) -> IDatabaseConnectionContext:
        return get_database_service().get_connection()

    def get_session(self, conn: Optional[Any] = None) -> Session:
        return get_database_service().get_session(conn)

    def execute(self, sql: str, params: Optional[tuple] = None) -> Any:
        return get_database_service().execute(sql, params)

    def fetchone(
        self, sql: str, params: Optional[tuple] = None
    ) -> Optional[Any]:
        return get_database_service().fetchone(sql, params)

    def fetchall(self, sql: str, params: Optional[tuple] = None) -> List[Any]:
        return get_database_service().fetchall(sql, params)

    def executemany(self, sql: str, params_list: List[tuple]) -> Any:
        return get_database_service().executemany(sql, params_list)

    def execute_query(
        self, sql: str, params: Optional[tuple] = None
    ) -> List[Any]:
        return get_database_service().execute_query(sql, params)

    def execute_update(self, sql: str, params: Optional[tuple] = None) -> Any:
        return get_database_service().execute_update(sql, params)

    def execute_batch(self, sql: str, params_list: List[tuple]) -> Any:
        return get_database_service().execute_batch(sql, params_list)

    def get_table_stats(self) -> Dict[str, int]:
        return get_database_service().get_table_stats()

    def get_health(self) -> DatabaseHealth:
        return get_database_service().get_health()

    def get_stats(self) -> DatabaseStats:
        return get_database_service().get_stats()

    def init_schema(self) -> None:
        get_database_service().init_schema()

    def init_database(self) -> None:
        get_database_service().init_database()

    def __getattr__(self, name: str) -> Any:
        return getattr(get_database_service(), name)


default_database_service: IDatabaseService = _LazyDatabaseServiceProxy()


def is_deployed() -> bool:
    import os

    return bool(
        os.getenv("AWS_LAMBDA_FUNCTION_NAME")
        or os.getenv("STAGE") == "prod"
        or os.getenv("LAMBDA_TASK_ROOT")
    )


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
