"""PostgreSQL-first database service.

Business logic always uses PostgreSQL (via DATABASE_URL).
SQLite is only used when ``db_path`` is explicitly passed in the constructor —
this path exists solely for test isolation (tmp_path fixtures) and should never
be reached in production or staging code.
"""

import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from sqlmodel import Session, SQLModel, create_engine, text

from src.services.database.types import (
    DatabaseHealth,
    DatabaseStats,
    IDatabaseService,
)
from src.services.logger import get_logger

logger = get_logger("services.database")


class DatabaseConnectionContext:
    """Connection proxy supporting both context-manager and direct usage."""

    def __init__(self, conn: Any):
        self._conn = conn

    def __enter__(self) -> Any:
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb):
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


class DatabaseService(IDatabaseService):
    def __init__(
        self,
        db_path: Optional[Union[Path, str]] = None,
        database_url: Optional[str] = None,
    ):
        # ------------------------------------------------------------------ #
        # db_path is reserved for test isolation only (SQLite in tmp_path).  #
        # In production/staging this should always be None.                  #
        # ------------------------------------------------------------------ #
        if db_path is not None and isinstance(db_path, str):
            db_path = Path(db_path)
        self._custom_db_path = db_path
        self._pg_engine = None

        if self._custom_db_path is None:
            # Normal path: always PostgreSQL
            url = database_url or os.getenv("DATABASE_URL", "")
            if url.startswith("postgres://"):
                url = "postgresql+psycopg://" + url[len("postgres://"):]
            elif url.startswith("postgresql://") and "+psycopg" not in url:
                url = "postgresql+psycopg://" + url[len("postgresql://"):]
            if not url:
                logger.warning(
                    "DATABASE_URL is not set — DatabaseService has no connection. "
                    "Set DATABASE_URL in your .env to point at the PostgreSQL instance."
                )
            else:
                try:
                    self._pg_engine = create_engine(
                        url,
                        pool_size=20,
                        max_overflow=10,
                        pool_pre_ping=True,
                    )
                    logger.info("DatabaseService initialized with PostgreSQL connection pool")
                except Exception as e:
                    logger.error(f"Failed to initialize PostgreSQL engine: {e}")
                    raise

        self._schema_initialized = False

    @property
    def is_postgres(self) -> bool:
        return self._pg_engine is not None

    def _get_raw_connection(self) -> Any:
        if self._pg_engine is not None:
            return self._pg_engine.raw_connection()

        # Test-only path: SQLite backed by a tmp file
        if self._custom_db_path is not None:
            conn = sqlite3.connect(self._custom_db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            return conn

        raise RuntimeError(
            "No database connection available. "
            "Ensure DATABASE_URL is set in your environment."
        )

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

        if self._pg_engine is not None:
            if conn is not None:
                # Wrap an existing raw pg connection
                raw = conn
                if hasattr(raw, "_conn"):
                    raw = raw._conn
                if hasattr(raw, "raw_connection"):
                    raw = raw.raw_connection
                # For postgres, sessions bind to the engine (connection pooling handles it)
                return Session(self._pg_engine)
            return Session(self._pg_engine)

        # Test-only SQLite path
        if self._custom_db_path is not None:
            raw = conn if conn is not None else self._get_raw_connection()
            if hasattr(raw, "_conn"):
                raw = raw._conn
            if hasattr(raw, "raw_connection"):
                raw = raw.raw_connection
            if isinstance(raw, sqlite3.Connection):
                engine = create_engine("sqlite://", creator=lambda: raw)
                return Session(engine)
            engine = create_engine("sqlite://", creator=lambda: raw)
            return Session(engine)

        raise RuntimeError(
            "No database engine available. "
            "Ensure DATABASE_URL is set in your environment."
        )

    def get_connection(self) -> DatabaseConnectionContext:
        self.ensure_schema()
        conn = self._get_raw_connection()
        return DatabaseConnectionContext(conn)

    def execute(self, sql: str, params: Optional[tuple] = None) -> Any:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            conn.commit()
            return cursor

    def fetchone(self, sql: str, params: Optional[tuple] = None) -> Any:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            return cursor.fetchone()

    def fetchall(self, sql: str, params: Optional[tuple] = None) -> List[Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            return cursor.fetchall()

    def executemany(self, sql: str, params_list: List[tuple]) -> Any:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(sql, params_list)
            conn.commit()
            return cursor

    def execute_query(self, sql: str, params: Optional[tuple] = None) -> List[Any]:
        return self.fetchall(sql, params)

    def execute_update(self, sql: str, params: Optional[tuple] = None) -> Any:
        return self.execute(sql, params)

    def execute_batch(self, sql: str, params_list: List[tuple]) -> Any:
        return self.executemany(sql, params_list)

    def get_table_stats(self) -> Dict[str, int]:
        """Return row counts for all user tables in the database."""
        stats: Dict[str, int] = {}
        if self.is_postgres:
            with self.get_session() as session:
                tables_res = session.connection().execute(
                    text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
                ).fetchall()
                tables = [r[0] if isinstance(r, (tuple, list)) else r for r in tables_res]
                for t in tables:
                    try:
                        cnt_res = session.connection().execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
                        stats[str(t)] = int(cnt_res or 0)
                    except Exception:
                        stats[str(t)] = 0
            return stats

        # Test-only SQLite path
        with self.get_connection() as conn:
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
        """Inspects database connectivity, schema tables, and storage status."""
        tables = []
        status = "healthy"
        details: Dict[str, Any] = {}
        engine_type = "postgresql" if self.is_postgres else "sqlite3 (test-only)"
        location = "ec2-postgres" if self.is_postgres else str(self._custom_db_path or "none")

        try:
            table_stats = self.get_table_stats()
            tables = list(table_stats.keys())
            details["table_count"] = len(tables)
            details["is_postgres"] = self.is_postgres
        except Exception as e:
            status = "degraded"
            details["error"] = str(e)
            logger.error("Database health check encountered error", error=str(e))

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
        """Retrieves aggregated entity counts across accounts, domains, signals, assets, and scores."""
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

    def init_database(self) -> None:
        """Alias for init_schema to initialize database tables and indexes."""
        self.init_schema()

    def init_schema(self) -> None:
        if self._pg_engine is not None:
            with self._pg_engine.connect() as conn:
                try:
                    conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
                    conn.commit()
                except Exception:
                    pass
            SQLModel.metadata.create_all(self._pg_engine)
            return

        # Test-only SQLite schema bootstrap
        if self._custom_db_path is None:
            raise RuntimeError(
                "Cannot initialize schema: no PostgreSQL engine and no test db_path provided."
            )

        conn = self._get_raw_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_key TEXT UNIQUE NOT NULL,
                    signal_count INTEGER DEFAULT 0,
                    priority_tier TEXT DEFAULT 'tier_4_low',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS domains (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    domain TEXT NOT NULL,
                    FOREIGN KEY(account_id) REFERENCES accounts(id),
                    UNIQUE(account_id, domain)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS assets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    ip TEXT,
                    port INTEGER,
                    hostname TEXT,
                    FOREIGN KEY(account_id) REFERENCES accounts(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ips (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    ip TEXT NOT NULL,
                    FOREIGN KEY(account_id) REFERENCES accounts(id),
                    UNIQUE(account_id, ip)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hostnames (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    hostname TEXT NOT NULL,
                    FOREIGN KEY(account_id) REFERENCES accounts(id),
                    UNIQUE(account_id, hostname)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    port INTEGER NOT NULL,
                    FOREIGN KEY(account_id) REFERENCES accounts(id),
                    UNIQUE(account_id, port)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    product TEXT NOT NULL,
                    FOREIGN KEY(account_id) REFERENCES accounts(id),
                    UNIQUE(account_id, product)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cloud_providers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    provider TEXT NOT NULL,
                    FOREIGN KEY(account_id) REFERENCES accounts(id),
                    UNIQUE(account_id, provider)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    category TEXT NOT NULL,
                    evidence TEXT NOT NULL,
                    FOREIGN KEY(account_id) REFERENCES accounts(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_key TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    score INTEGER NOT NULL,
                    priority_tier TEXT NOT NULL,
                    key_risks TEXT NOT NULL,
                    suggested_outreach TEXT NOT NULL,
                    score_rationale TEXT DEFAULT '',
                    model_version TEXT NOT NULL,
                    model_name TEXT DEFAULT 'gemini-3.1-flash-lite',
                    tokens_used TEXT,
                    latency_ms INTEGER DEFAULT 0,
                    cost_usd REAL DEFAULT 0.0,
                    scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_latest INTEGER DEFAULT 1
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    full_name TEXT,
                    role TEXT DEFAULT 'member',
                    gemini_api_key TEXT,
                    api_key TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS background_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT UNIQUE NOT NULL,
                    job_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    user_id INTEGER,
                    status TEXT NOT NULL DEFAULT 'queued',
                    progress_current INTEGER NOT NULL DEFAULT 0,
                    progress_total INTEGER NOT NULL DEFAULT 0,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 3,
                    payload_json TEXT NOT NULL,
                    results_json TEXT,
                    metadata_json TEXT,
                    error_message TEXT,
                    trace_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS crawler_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT UNIQUE NOT NULL,
                    user_id INTEGER,
                    status TEXT NOT NULL DEFAULT 'queued',
                    scan_depth TEXT NOT NULL DEFAULT 'standard',
                    enable_subdomains INTEGER DEFAULT 1,
                    custom_ports TEXT,
                    save_to_database INTEGER DEFAULT 1,
                    domains_input TEXT NOT NULL,
                    domains_count INTEGER DEFAULT 0,
                    completed_count INTEGER DEFAULT 0,
                    assets_discovered_count INTEGER DEFAULT 0,
                    signals_detected_count INTEGER DEFAULT 0,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    results_json TEXT,
                    error_message TEXT,
                    trace_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS eval_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT UNIQUE NOT NULL,
                    prompt_version TEXT NOT NULL,
                    total_samples INTEGER NOT NULL,
                    tier_accuracy REAL NOT NULL,
                    macro_f1 REAL NOT NULL,
                    weighted_f1 REAL NOT NULL,
                    critical_threat_recall REAL NOT NULL,
                    score_tier_consistency REAL NOT NULL,
                    score_mae REAL NOT NULL,
                    score_rmse REAL NOT NULL,
                    within_5_points INTEGER NOT NULL,
                    within_5_points_pct REAL NOT NULL,
                    tier_metrics_json TEXT NOT NULL,
                    predictions_json TEXT NOT NULL,
                    results_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            indices = [
                "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
                "CREATE INDEX IF NOT EXISTS idx_account_key ON accounts(account_key)",
                "CREATE INDEX IF NOT EXISTS idx_accounts_signal_count ON accounts(signal_count DESC)",
                "CREATE INDEX IF NOT EXISTS idx_accounts_tier_signal_count ON accounts(priority_tier, signal_count DESC)",
                "CREATE INDEX IF NOT EXISTS idx_domain ON domains(domain)",
                "CREATE INDEX IF NOT EXISTS idx_domains_account_id ON domains(account_id)",
                "CREATE INDEX IF NOT EXISTS idx_assets_account_id ON assets(account_id)",
                "CREATE INDEX IF NOT EXISTS idx_ips_account_id ON ips(account_id)",
                "CREATE INDEX IF NOT EXISTS idx_ips_ip ON ips(ip)",
                "CREATE INDEX IF NOT EXISTS idx_hostnames_account_id ON hostnames(account_id)",
                "CREATE INDEX IF NOT EXISTS idx_ports_account_id ON ports(account_id)",
                "CREATE INDEX IF NOT EXISTS idx_products_account_id ON products(account_id)",
                "CREATE INDEX IF NOT EXISTS idx_cloud_providers_account_id ON cloud_providers(account_id)",
                "CREATE INDEX IF NOT EXISTS idx_signals_account_id ON signals(account_id)",
                "CREATE INDEX IF NOT EXISTS idx_signal_severity ON signals(severity)",
                "CREATE INDEX IF NOT EXISTS idx_signal_name ON signals(name)",
                "CREATE INDEX IF NOT EXISTS idx_signals_acc_sev ON signals(account_id, severity)",
                "CREATE INDEX IF NOT EXISTS idx_signals_sev_acc ON signals(severity, account_id)",
                "CREATE INDEX IF NOT EXISTS idx_signals_name_acc ON signals(name, account_id)",
                "CREATE INDEX IF NOT EXISTS idx_assets_cov ON assets(account_id, ip, port, hostname)",
                "CREATE INDEX IF NOT EXISTS idx_signals_cov ON signals(account_id, name, severity, category, evidence)",
                "CREATE INDEX IF NOT EXISTS idx_ai_scores_acc_key ON ai_scores(account_key)",
                "CREATE INDEX IF NOT EXISTS idx_ai_scores_latest ON ai_scores(account_key, is_latest)",
                "CREATE INDEX IF NOT EXISTS idx_ai_scores_scored_at ON ai_scores(scored_at DESC)",
                "CREATE INDEX IF NOT EXISTS idx_bg_jobs_id ON background_jobs(job_id)",
                "CREATE INDEX IF NOT EXISTS idx_bg_jobs_type_status ON background_jobs(job_type, status)",
                "CREATE INDEX IF NOT EXISTS idx_bg_jobs_created_at ON background_jobs(created_at DESC)",
                "CREATE INDEX IF NOT EXISTS idx_eval_runs_id ON eval_runs(run_id)",
                "CREATE INDEX IF NOT EXISTS idx_eval_runs_prompt_ver ON eval_runs(prompt_version)",
                "CREATE INDEX IF NOT EXISTS idx_eval_runs_created_at ON eval_runs(created_at DESC)",
            ]
            for idx_sql in indices:
                cursor.execute(idx_sql)

            conn.commit()
            self._schema_initialized = True
            logger.info("Test SQLite schema initialized successfully")
        finally:
            conn.close()
