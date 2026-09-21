import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from src.core.config import SUMMARY_CACHE_TTL_SECONDS
from src.services.accounts.repositories.reader import AccountReader
from src.services.accounts.repositories.writer import AccountWriter
from src.services.accounts.types import (
    Account,
    IAccountReader,
    IAccountsService,
    IAccountWriter,
    SignalSeverity,
)
from src.services.database import default_database_service
from src.services.database.database_service import DatabaseService
from src.services.logger import get_logger

logger = get_logger("services.accounts")


class AccountsService(IAccountsService):
    def __init__(
        self,
        db_path: Optional[Union[Path, str]] = None,
        reader: Optional[IAccountReader] = None,
        writer: Optional[IAccountWriter] = None,
    ):
        self.db_path = Path(db_path) if isinstance(db_path, str) else db_path
        self._local_db_service = DatabaseService(db_path=self.db_path) if self.db_path is not None else None
        self.reader = reader or AccountReader()
        self.writer = writer or AccountWriter()
        self._summary_cache: Optional[Dict[str, int]] = None
        self._summary_cache_time: float = 0.0

    def _db_conn(self):
        """Return the appropriate DB connection context (local SQLite for tests, global Postgres for prod)."""
        svc = self._local_db_service if self._local_db_service is not None else default_database_service
        return svc.get_connection()

    def compute_priority_tier(self, account: Account) -> str:
        has_critical = any(
            s.severity == "critical"
            or s.severity == SignalSeverity.CRITICAL
            or getattr(s.severity, "value", None) == "critical"
            for s in account.signals
        )
        has_high = any(
            s.severity == "high" or s.severity == SignalSeverity.HIGH or getattr(s.severity, "value", None) == "high"
            for s in account.signals
        )
        num_signals = len(account.signals)

        if has_critical:
            return "tier_1_critical"
        elif has_high and num_signals >= 2:
            return "tier_2_high"
        elif has_high or num_signals > 0:
            return "tier_3_medium"
        else:
            return "tier_4_low"

    def get_account(self, account_key: str, version: Optional[str] = None) -> Optional[Account]:
        with logger.span("accounts.get_account", account_key=account_key, version=version):
            with self._db_conn() as conn:
                account = self.reader.load_account(conn, account_key, version=version)
                if not account:
                    logger.warning("Account not found", account_key=account_key, version=version)
                return account

    def get_account_versions(self, account_key: str) -> List[Any]:
        with logger.span("accounts.get_versions", account_key=account_key):
            with self._db_conn() as conn:
                return self.reader.get_account_versions(conn, account_key)

    def get_accounts_batch(self, account_keys: List[str], as_dict: bool = False) -> List[Any]:
        with logger.span("accounts.get_batch", count=len(account_keys)):
            with self._db_conn() as conn:
                return self.reader.load_accounts_batch(conn, account_keys, as_dict=as_dict)

    def search_accounts(self, query: str, limit: int = 10) -> List[Any]:
        with logger.span("accounts.search", query=query, limit=limit):
            with self._db_conn() as conn:
                keys = self.reader.search_accounts_by_domain(conn, query, limit=limit)
                items = self.reader.load_accounts_summary_batch(conn, keys)
                logger.info("Account search completed", query=query, results_count=len(items))
                return items

    def list_accounts(
        self,
        skip: int = 0,
        limit: int = 20,
        priority_tier: Optional[str] = None,
        has_critical_signals: Optional[bool] = None,
    ) -> Tuple[List[Any], int]:
        with logger.span("accounts.list", skip=skip, limit=limit, priority_tier=priority_tier):
            stats = self.get_summary_stats()
            with self._db_conn() as conn:
                if priority_tier and priority_tier != "all":
                    tier_total = stats.get(
                        priority_tier.replace("tier_1_critical", "critical_count")
                        .replace("tier_2_high", "high_count")
                        .replace("tier_3_medium", "medium_count")
                        .replace("tier_4_low", "low_count"),
                        None,
                    )
                    keys, total = self.reader.get_accounts_by_priority_tier(
                        conn, priority_tier, skip=skip, limit=limit, total=tier_total
                    )
                elif has_critical_signals:
                    keys, total = self.reader.get_accounts_with_critical_signals(
                        conn, skip=skip, limit=limit, total=stats.get("accounts_with_critical_signals")
                    )
                else:
                    keys, total = self.reader.get_all_accounts(
                        conn, skip=skip, limit=limit, total=stats.get("total_accounts")
                    )

                items = self.reader.load_accounts_summary_batch(conn, keys)
                return items, total

    def get_accounts_by_signal(self, signal_name: str, skip: int = 0, limit: int = 20) -> Tuple[List[Any], int]:
        with logger.span("accounts.by_signal", signal=signal_name, skip=skip, limit=limit):
            with self._db_conn() as conn:
                keys, total = self.reader.get_accounts_by_signal(conn, signal_name, skip=skip, limit=limit)
                items = self.reader.load_accounts_summary_batch(conn, keys)
                return items, total

    def get_summary_stats(self, force_refresh: bool = False) -> Dict[str, int]:
        now = time.time()
        if (
            not force_refresh
            and self._summary_cache is not None
            and (now - self._summary_cache_time) < SUMMARY_CACHE_TTL_SECONDS
        ):
            return self._summary_cache

        with logger.span("accounts.summary_stats", force_refresh=force_refresh):
            with self._db_conn() as conn:
                stats = self.reader.get_summary_stats(conn)
                self._summary_cache = stats
                self._summary_cache_time = now
                return stats

    def save_account(self, account: Account) -> int:
        tier = self.compute_priority_tier(account)
        with logger.span("accounts.save", account_key=account.account_key, tier=tier):
            with self._db_conn() as conn:
                acc_id = self.writer.insert_account(conn, account, tier)
                conn.commit()
                self._summary_cache = None
                logger.info("Account saved successfully", account_id=acc_id, account_key=account.account_key, tier=tier)
                return acc_id

    def delete_account(self, account_key: str) -> bool:
        with logger.span("accounts.delete", account_key=account_key):
            with self._db_conn() as conn:
                res = self.writer.delete_account(conn, account_key)
                conn.commit()
                self._summary_cache = None
                return res

    def clear_all(self) -> None:
        with logger.span("accounts.clear_all"):
            with self._db_conn() as conn:
                self.writer.clear_accounts(conn)
                conn.commit()
                self._summary_cache = None
                logger.info("All accounts cleared")


default_accounts_service = AccountsService()
