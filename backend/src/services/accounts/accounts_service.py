import time
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any

from src.services.database import get_db_connection, is_deployed
from src.core.config import SUMMARY_CACHE_TTL_SECONDS
from src.services.accounts.types import (
    IAccountsService,
    IAccountReader,
    IAccountWriter,
    SummaryStats,
    Account,
    SignalSeverity,
)
from src.services.accounts.repositories.reader import AccountReader
from src.services.accounts.repositories.writer import AccountWriter
from src.services.accounts.repositories.dynamo_crawled import DynamoCrawledRepository
from src.services.logger import get_logger

logger = get_logger("services.accounts")


class AccountsService(IAccountsService):
    def __init__(
        self,
        db_path: Optional[Path] = None,
        reader: Optional[IAccountReader] = None,
        writer: Optional[IAccountWriter] = None,
        dynamo_crawled: Optional[DynamoCrawledRepository] = None,
    ):
        self.db_path = db_path
        self.reader = reader or AccountReader()
        self.writer = writer or AccountWriter()
        self.dynamo_crawled = dynamo_crawled or (DynamoCrawledRepository() if is_deployed() else None)
        self._summary_cache: Optional[Dict[str, int]] = None
        self._summary_cache_time: float = 0.0

    def compute_priority_tier(self, account: Account) -> str:
        has_critical = any(
            s.severity == "critical" or s.severity == SignalSeverity.CRITICAL or getattr(s.severity, "value", None) == "critical"
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

    def get_account(self, account_key: str) -> Optional[Account]:
        with logger.span("accounts.get_account", account_key=account_key):
            with get_db_connection(self.db_path) as conn:
                account = self.reader.load_account(conn, account_key)
                if not account and self.dynamo_crawled:
                    account = self.dynamo_crawled.get_crawled_account(account_key)
                if not account:
                    logger.warning("Account not found", account_key=account_key)
                return account

    def get_accounts_batch(self, account_keys: List[str], as_dict: bool = False) -> List[Any]:
        with logger.span("accounts.get_batch", count=len(account_keys)):
            with get_db_connection(self.db_path) as conn:
                return self.reader.load_accounts_batch(conn, account_keys, as_dict=as_dict)

    def search_accounts(self, query: str, limit: int = 10) -> List[Any]:
        with logger.span("accounts.search", query=query, limit=limit):
            with get_db_connection(self.db_path) as conn:
                keys = self.reader.search_accounts_by_domain(conn, query, limit=limit)
                items = self.reader.load_accounts_summary_batch(conn, keys)

                if self.dynamo_crawled:
                    try:
                        crawled_items = self.dynamo_crawled.search_crawled_accounts(query, limit=limit)
                        existing_keys = {it.get("account_key") for it in items}
                        for c_item in crawled_items:
                            if c_item.get("account_key") not in existing_keys:
                                items.append(c_item)
                                existing_keys.add(c_item.get("account_key"))
                        items = items[:limit]
                    except Exception as e:
                        logger.warning(f"Error merging DynamoDB crawled search results: {e}")

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
            with get_db_connection(self.db_path) as conn:
                cursor = conn.cursor()
                if priority_tier and priority_tier != "all":
                    total = stats.get(priority_tier, stats.get("total_accounts", 0))
                    cursor.execute(
                        "SELECT account_key FROM accounts WHERE priority_tier = ? ORDER BY signal_count DESC, id ASC LIMIT ? OFFSET ?",
                        (priority_tier, limit, skip),
                    )
                    keys = [r[0] for r in cursor.fetchall()]
                elif has_critical_signals:
                    total = stats.get("critical_count", 0)
                    cursor.execute(
                        "SELECT account_key FROM accounts WHERE priority_tier = 'tier_1_critical' ORDER BY signal_count DESC, id ASC LIMIT ? OFFSET ?",
                        (limit, skip),
                    )
                    keys = [r[0] for r in cursor.fetchall()]
                else:
                    total = stats.get("total_accounts", 0)
                    cursor.execute(
                        "SELECT account_key FROM accounts ORDER BY signal_count DESC, id ASC LIMIT ? OFFSET ?",
                        (limit, skip),
                    )
                    keys = [r[0] for r in cursor.fetchall()]

                items = self.reader.load_accounts_summary_batch(conn, keys)
                return items, total

    def get_accounts_by_signal(self, signal_name: str, skip: int = 0, limit: int = 20) -> Tuple[List[Any], int]:
        with logger.span("accounts.by_signal", signal=signal_name, skip=skip, limit=limit):
            with get_db_connection(self.db_path) as conn:
                keys, total = self.reader.get_accounts_by_signal(conn, signal_name, skip=skip, limit=limit)
                items = self.reader.load_accounts_summary_batch(conn, keys)
                return items, total

    def get_summary_stats(self, force_refresh: bool = False) -> Dict[str, int]:
        now = time.time()
        if not force_refresh and self._summary_cache is not None and (now - self._summary_cache_time) < SUMMARY_CACHE_TTL_SECONDS:
            return self._summary_cache

        with logger.span("accounts.summary_stats", force_refresh=force_refresh):
            with get_db_connection(self.db_path) as conn:
                stats = self.reader.get_summary_stats(conn)
                self._summary_cache = stats
                self._summary_cache_time = now
                return stats

    def save_account(self, account: Account) -> int:
        tier = self.compute_priority_tier(account)
        with logger.span("accounts.save", account_key=account.account_key, tier=tier):
            if self.dynamo_crawled:
                try:
                    self.dynamo_crawled.save_crawled_account(account, tier)
                except Exception as e:
                    logger.warning(f"Failed to persist crawled account to DynamoDB: {e}")

            with get_db_connection(self.db_path) as conn:
                acc_id = self.writer.insert_account(conn, account, tier)
                conn.commit()
                self._summary_cache = None
                logger.info("Account saved successfully", account_id=acc_id, account_key=account.account_key, tier=tier)
                return acc_id

    def clear_all(self) -> None:
        with logger.span("accounts.clear_all"):
            with get_db_connection(self.db_path) as conn:
                self.writer.clear_accounts(conn)
                conn.commit()
                self._summary_cache = None
                logger.info("All accounts cleared")


default_accounts_service = AccountsService()
