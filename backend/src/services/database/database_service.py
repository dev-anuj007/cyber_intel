from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from sqlmodel import Session

from src.services.database.dependencies import (
    DatabaseServiceDependencyContext,
    get_database_dependency_context,
)
from src.services.database.internals.connection import DatabaseConnectionContext
from src.services.database.protocols import (
    IDatabaseConnectionContext,
    IDatabaseReader,
    IDatabaseService,
    IDatabaseSessionManager,
    IDatabaseWriter,
)
from src.services.database.types import (
    DatabaseHealth,
    DatabaseStats,
)
from src.services.logger.logger_service import get_logger

logger = get_logger("services.database")


class DatabaseService(IDatabaseService):
    def __init__(
        self,
        context: Optional[DatabaseServiceDependencyContext] = None,
        db_path: Optional[Union[Path, str]] = None,
        database_url: Optional[str] = None,
    ):
        if context is None:
            context = get_database_dependency_context(db_path=db_path, database_url=database_url)

        self._context = context
        self._session_manager: IDatabaseSessionManager = context.session_manager
        self._reader: IDatabaseReader = context.reader
        self._writer: IDatabaseWriter = context.writer
        self._schema_initialized = False

    @property
    def is_postgres(self) -> bool:
        return self._session_manager.is_postgres

    @property
    def _pg_engine(self) -> Any:
        return getattr(self._session_manager, "pg_engine", None)

    @property
    def _custom_db_path(self) -> Optional[Path]:
        return getattr(self._session_manager, "custom_db_path", None)

    def _get_raw_connection(self) -> Any:
        return self._session_manager.get_raw_connection()

    def ensure_schema(self) -> None:
        if self._schema_initialized:
            return
        self._schema_initialized = True
        try:
            self.init_schema()
        except Exception as e:
            self._schema_initialized = False
            logger.warning(f"Database schema initialization notice: {e}")

    def get_session(self, conn: Optional[Any] = None) -> Session:
        self.ensure_schema()
        return self._session_manager.get_session(conn)

    def get_connection(self) -> IDatabaseConnectionContext:
        self.ensure_schema()
        return self._session_manager.get_connection()

    def execute(self, sql: str, params: Optional[tuple] = None) -> Any:
        self.ensure_schema()
        return self._writer.execute(sql, params)

    def fetchone(self, sql: str, params: Optional[tuple] = None) -> Optional[Any]:
        self.ensure_schema()
        return self._reader.fetchone(sql, params)

    def fetchall(self, sql: str, params: Optional[tuple] = None) -> List[Any]:
        self.ensure_schema()
        return self._reader.fetchall(sql, params)

    def executemany(self, sql: str, params_list: List[tuple]) -> Any:
        self.ensure_schema()
        return self._writer.executemany(sql, params_list)

    def execute_query(self, sql: str, params: Optional[tuple] = None) -> List[Any]:
        return self.fetchall(sql, params)

    def execute_update(self, sql: str, params: Optional[tuple] = None) -> Any:
        return self.execute(sql, params)

    def execute_batch(self, sql: str, params_list: List[tuple]) -> Any:
        return self.executemany(sql, params_list)

    def get_table_stats(self) -> Dict[str, int]:
        return self._reader.get_table_stats()

    def get_health(self) -> DatabaseHealth:
        return self._reader.get_health()

    def get_stats(self) -> DatabaseStats:
        return self._reader.get_stats()

    def init_database(self) -> None:
        self.init_schema()

    def init_schema(self) -> None:
        self._writer.init_schema()
        self._schema_initialized = True
