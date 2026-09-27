from typing import Any, List, Optional
from sqlmodel import SQLModel, text

from src.services.database.internals.repositories.models import (
    SQLITE_INDEX_STATEMENTS,
    SQLITE_SCHEMA_STATEMENTS,
)
from src.services.database.protocols import IDatabaseSessionManager
from src.services.logger.logger_service import get_logger

logger = get_logger("services.database.writer")


class DatabaseWriter:
    def __init__(self, session_manager: IDatabaseSessionManager):
        self._session_manager = session_manager
        self._schema_initialized = False

    def execute(self, sql: str, params: Optional[tuple] = None) -> Any:
        with self._session_manager.get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            conn.commit()
            return cursor

    def executemany(self, sql: str, params_list: List[tuple]) -> Any:
        with self._session_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(sql, params_list)
            conn.commit()
            return cursor

    def execute_update(self, sql: str, params: Optional[tuple] = None) -> Any:
        return self.execute(sql, params)

    def execute_batch(self, sql: str, params_list: List[tuple]) -> Any:
        return self.executemany(sql, params_list)

    def init_schema(self) -> None:
        if self._session_manager.is_postgres:
            pg_engine = getattr(self._session_manager, "pg_engine", None)
            if pg_engine is not None:
                with pg_engine.connect() as conn:
                    try:
                        conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
                        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
                        conn.commit()
                    except Exception:
                        pass
                SQLModel.metadata.create_all(pg_engine)
                self._schema_initialized = True
                return

        custom_path = getattr(self._session_manager, "custom_db_path", None)
        if custom_path is None:
            raise RuntimeError("Cannot initialize schema: no PostgreSQL engine and no test db_path provided.")

        conn = self._session_manager.get_raw_connection()
        try:
            cursor = conn.cursor()
            for stmt in SQLITE_SCHEMA_STATEMENTS:
                cursor.execute(stmt)

            for idx_stmt in SQLITE_INDEX_STATEMENTS:
                cursor.execute(idx_stmt)

            conn.commit()
            self._schema_initialized = True
            logger.info("Test SQLite schema initialized successfully")
        finally:
            conn.close()
