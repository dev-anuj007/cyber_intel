import sqlite3
import time
from pathlib import Path
from typing import Optional, List, Tuple, Any, Dict
from contextlib import contextmanager

from src.services.database.types import (
    IDatabaseService,
    DatabaseHealth,
    DatabaseStats,
)
from src.services.database.s3_storage import S3DirectStorage
from src.services.logger import get_logger

logger = get_logger("services.database")


class DatabaseService(IDatabaseService):

    def __init__(
        self,
        db_path: Optional[Path] = None,
        s3_storage: Optional[S3DirectStorage] = None,
    ):
        self._custom_db_path = db_path
        self.s3_storage = s3_storage or S3DirectStorage(local_path=db_path)
        self._schema_initialized = False

    def _get_raw_connection(self) -> sqlite3.Connection:
        if self._custom_db_path is not None:
            effective_path = self._custom_db_path
        else:
            effective_path = self.s3_storage.get_effective_db_path()

        conn = sqlite3.connect(effective_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_schema(self) -> None:
        if self._schema_initialized:
            return
        self._schema_initialized = True
        try:
            self.init_schema()
        except Exception as e:
            self._schema_initialized = False
            logger.warning(f"Database schema initialization notice: {e}")

    @contextmanager
    def get_connection(self):
        self.ensure_schema()
        conn = self._get_raw_connection()
        try:
            yield conn
        finally:
            conn.close()

    def execute(self, sql: str, params: Optional[tuple] = None) -> sqlite3.Cursor:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            conn.commit()

        if sql.strip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER")):
            self.s3_storage.sync_to_s3()

        return cursor

    def fetchone(self, sql: str, params: Optional[tuple] = None) -> Optional[sqlite3.Row]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            return cursor.fetchone()

    def fetchall(self, sql: str, params: Optional[tuple] = None) -> List[sqlite3.Row]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            return cursor.fetchall()

    def executemany(self, sql: str, params_list: List[tuple]) -> sqlite3.Cursor:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(sql, params_list)
            conn.commit()

        if sql.strip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER")):
            self.s3_storage.sync_to_s3()

        return cursor

    def get_health(self) -> DatabaseHealth:
        """Inspects database connectivity, schema tables, and storage status."""
        location, size_bytes, is_s3 = self.s3_storage.get_storage_info()
        tables = []
        status = "healthy"
        details: Dict[str, Any] = {}

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [r[0] for r in cursor.fetchall() if not r[0].startswith("sqlite_")]
                details["table_count"] = len(tables)
        except Exception as e:
            status = "degraded"
            details["error"] = str(e)
            logger.error("Database health check encountered error", error=str(e))

        return DatabaseHealth(
            status=status,
            engine="sqlite3",
            storage_location=location,
            size_bytes=size_bytes,
            tables=tables,
            s3_direct_enabled=is_s3,
            details=details,
        )

    def get_stats(self) -> DatabaseStats:
        """Retrieves aggregated entity counts across accounts, domains, signals, assets, and scores."""
        stats = DatabaseStats()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                for table, attr in [
                    ("accounts", "total_accounts"),
                    ("domains", "total_domains"),
                    ("signals", "total_signals"),
                    ("assets", "total_assets"),
                    ("ai_scores", "total_scores"),
                    ("users", "total_users"),
                    ("background_jobs", "total_jobs"),
                ]:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        row = cursor.fetchone()
                        if row:
                            setattr(stats, attr, row[0])
                    except sqlite3.OperationalError:
                        setattr(stats, attr, 0)
        except Exception as e:
            logger.warning(f"Error fetching database stats: {e}")

        return stats

    def init_schema(self) -> None:
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

            cursor.execute("PRAGMA table_info(accounts)")
            existing_cols = [c[1] for c in cursor.fetchall()]
            if "signal_count" not in existing_cols:
                cursor.execute("ALTER TABLE accounts ADD COLUMN signal_count INTEGER DEFAULT 0")
            if "priority_tier" not in existing_cols:
                cursor.execute("ALTER TABLE accounts ADD COLUMN priority_tier TEXT DEFAULT 'tier_4_low'")

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
                    gemini_api_key TEXT,
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
            logger.info("Database schema initialized and verified successfully")
        finally:
            conn.close()
