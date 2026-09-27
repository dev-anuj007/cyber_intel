from typing import Any, Dict, List, Optional
from sqlmodel import text

from src.services.database.protocols import IDatabaseSessionManager
from src.services.database.types import DatabaseHealth, DatabaseStats
from src.services.logger.logger_service import get_logger

logger = get_logger("services.database.reader")


class DatabaseReader:
    def __init__(self, session_manager: IDatabaseSessionManager):
        self._session_manager = session_manager

    def fetchone(self, sql: str, params: Optional[tuple] = None) -> Optional[Any]:
        with self._session_manager.get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            return cursor.fetchone()

    def fetchall(self, sql: str, params: Optional[tuple] = None) -> List[Any]:
        with self._session_manager.get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            return cursor.fetchall()

    def execute_query(self, sql: str, params: Optional[tuple] = None) -> List[Any]:
        return self.fetchall(sql, params)

    def get_table_stats(self) -> Dict[str, int]:
        stats: Dict[str, int] = {}
        if self._session_manager.is_postgres:
            with self._session_manager.get_session() as session:
                tables_res = (
                    session.connection()
                    .execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))
                    .fetchall()
                )
                tables = [r[0] if isinstance(r, (tuple, list)) else r for r in tables_res]
                for t in tables:
                    try:
                        cnt_res = session.connection().execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
                        stats[str(t)] = int(cnt_res or 0)
                    except Exception:
                        stats[str(t)] = 0
            return stats

        with self._session_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cursor.fetchall() if not r[0].startswith("sqlite_")]
            for t in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {t}")
                    row = cursor.fetchone()
                    stats[t] = row[0] if row else 0
                except Exception:
                    stats[t] = 0
        return stats

    def get_health(self) -> DatabaseHealth:
        tables = []
        status = "healthy"
        details: Dict[str, Any] = {}
        is_pg = self._session_manager.is_postgres
        engine_type = "postgresql" if is_pg else "sqlite3 (test-only)"
        custom_path = getattr(self._session_manager, "custom_db_path", None)
        location = "ec2-postgres" if is_pg else str(custom_path or "none")

        try:
            table_stats = self.get_table_stats()
            tables = list(table_stats.keys())
            details["table_count"] = len(tables)
            details["is_postgres"] = is_pg
        except Exception as e:
            status = "degraded"
            details["error"] = str(e)
            logger.error(f"Database health check encountered error: {e}")

        return DatabaseHealth(
            status=status,
            engine=engine_type,
            storage_location=location,
            size_bytes=0,
            tables=tables,
            s3_direct_enabled=False,
            details=details,
        )

    def get_stats(self) -> DatabaseStats:
        stats = DatabaseStats()
        try:
            table_stats = self.get_table_stats()
            stats.total_accounts = table_stats.get("accounts", 0)
            stats.total_domains = table_stats.get("domains", 0)
            stats.total_signals = table_stats.get("signals", 0)
            stats.total_assets = table_stats.get("assets", 0)
            stats.total_scores = table_stats.get("ai_scores", 0)
            stats.total_users = table_stats.get("users", 0)
            stats.total_jobs = table_stats.get("background_jobs", 0)
        except Exception as e:
            logger.warning(f"Error fetching database stats: {e}")

        return stats
