import os
import sqlite3
from pathlib import Path
from typing import Any, Optional, Union

from sqlmodel import Session, create_engine

from src.services.database.types import DatabaseConfig
from src.services.logger.logger_service import get_logger

logger = get_logger("services.database.connection")


class DatabaseConnectionContext:
    def __init__(self, conn: Any):
        self._conn = conn

    def __enter__(self) -> Any:
        return self._conn

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass


class DatabaseSessionManager:
    def __init__(
        self,
        config: Optional[DatabaseConfig] = None,
        db_path: Optional[Union[Path, str]] = None,
        database_url: Optional[str] = None,
    ):
        if config is None:
            config = DatabaseConfig(db_path=db_path, database_url=database_url)

        self._custom_db_path: Optional[Path] = (
            Path(config.db_path) if config.db_path is not None else None
        )
        self._pg_engine = None

        if self._custom_db_path is None:
            url = config.database_url or os.getenv("DATABASE_URL", "")
            if url.startswith("postgres://"):
                url = "postgresql+psycopg://" + url[len("postgres://") :]
            elif url.startswith("postgresql://") and "+psycopg" not in url:
                url = "postgresql+psycopg://" + url[len("postgresql://") :]
            if not url:
                logger.warning(
                    "DATABASE_URL is not set — DatabaseService has no connection. "
                    "Set DATABASE_URL in your .env to point at the PostgreSQL instance."
                )
            else:
                try:
                    self._pg_engine = create_engine(
                        url,
                        pool_size=config.pool_size,
                        max_overflow=config.max_overflow,
                        pool_pre_ping=config.pool_pre_ping,
                    )
                    logger.info("DatabaseService initialized with PostgreSQL connection pool")
                except Exception as e:
                    logger.error(f"Failed to initialize PostgreSQL engine: {e}")
                    raise

    @property
    def is_postgres(self) -> bool:
        return self._pg_engine is not None

    @property
    def pg_engine(self) -> Any:
        return self._pg_engine

    @property
    def custom_db_path(self) -> Optional[Path]:
        return self._custom_db_path

    def get_raw_connection(self) -> Any:
        if self._pg_engine is not None:
            return self._pg_engine.raw_connection()

        if self._custom_db_path is not None:
            conn = sqlite3.connect(self._custom_db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            return conn

        raise RuntimeError("No database connection available. Ensure DATABASE_URL is set in your environment.")

    def _get_raw_connection(self) -> Any:
        return self.get_raw_connection()

    def get_connection(self) -> DatabaseConnectionContext:
        conn = self.get_raw_connection()
        return DatabaseConnectionContext(conn)

    def get_session(self, conn: Optional[Any] = None) -> Session:
        if self._pg_engine is not None:
            return Session(self._pg_engine)

        if self._custom_db_path is not None:
            raw = conn if conn is not None else self.get_raw_connection()
            if hasattr(raw, "_conn"):
                raw = raw._conn
            if hasattr(raw, "raw_connection"):
                raw = raw.raw_connection
            if isinstance(raw, sqlite3.Connection):
                engine = create_engine("sqlite://", creator=lambda: raw)
                return Session(engine)
            engine = create_engine("sqlite://", creator=lambda: raw)
            return Session(engine)

        raise RuntimeError("No database engine available. Ensure DATABASE_URL is set in your environment.")
