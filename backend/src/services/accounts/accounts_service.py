from typing import Any, List, Optional, Union

from src.services.accounts.dependencies import AccountsServiceDependencyContext
from src.services.accounts.protocols import IAccountsService
from src.services.accounts.types import (
    Account,
    AccountsBatchQuery,
    AccountsBySignalQuery,
    AccountsBySignalResponse,
    AccountSearchResponse,
    AccountsPaginatedResponse,
    AccountVersionsResponse,
    ClearAccountsResponse,
    DeleteAccountResponse,
    InsertAccountCommand,
    ListAccountsQuery,
    PriorityTier,
    SaveAccountResponse,
    SignalSeverity,
    SummaryStats,
)


class AccountsService(IAccountsService):
    def __init__(self, context: AccountsServiceDependencyContext):
        self.context = context

    def compute_priority_tier(self, account: Account) -> PriorityTier:
        severities = [
            (
                s.severity.value
                if isinstance(s.severity, SignalSeverity)
                else str(s.severity)
            ).lower()
            for s in account.signals
        ]
        has_critical = SignalSeverity.CRITICAL.value in severities
        has_high = SignalSeverity.HIGH.value in severities
        num_signals = len(account.signals)

        if has_critical:
            return PriorityTier.TIER_1_CRITICAL
        elif has_high and num_signals >= 2:
            return PriorityTier.TIER_2_HIGH
        elif has_high or num_signals > 0:
            return PriorityTier.TIER_3_MEDIUM
        else:
            return PriorityTier.TIER_4_LOW

    def get_account(
        self, account_key: str, version: Optional[str] = None
    ) -> Optional[Account]:
        with self.context.logger.span(
            "accounts.get_account", account_key=account_key, version=version
        ):
            with self.context.get_connection() as conn:
                account = self.context.reader.load_account(
                    conn, account_key, version=version
                )
                if not account:
                    self.context.logger.warning(
                        "Account not found", account_key=account_key, version=version
                    )
                return account

    def get_account_versions(self, account_key: str) -> AccountVersionsResponse:
        with self.context.logger.span("accounts.get_versions", account_key=account_key):
            with self.context.get_connection() as conn:
                versions = self.context.reader.get_account_versions(conn, account_key)
                return AccountVersionsResponse(
                    account_key=account_key,
                    total_versions=len(versions),
                    versions=versions,
                )

    def get_accounts_batch(
        self, account_keys: Union[List[str], AccountsBatchQuery], as_dict: bool = False
    ) -> List[Any]:
        if isinstance(account_keys, AccountsBatchQuery):
            target_keys = account_keys.account_keys
            target_as_dict = account_keys.as_dict
        else:
            target_keys = account_keys
            target_as_dict = as_dict

        with self.context.logger.span("accounts.get_batch", count=len(target_keys)):
            with self.context.get_connection() as conn:
                return self.context.reader.load_accounts_batch(
                    conn, target_keys, as_dict=target_as_dict
                )

    def search_accounts(self, query: str, limit: int = 10) -> AccountSearchResponse:
        with self.context.logger.span("accounts.search", query=query, limit=limit):
            with self.context.get_connection() as conn:
                keys = self.context.reader.search_accounts_by_domain(
                    conn, query, limit=limit
                )
                items = self.context.reader.load_accounts_summary_batch(conn, keys)
                self.context.logger.info(
                    "Account search completed", query=query, results_count=len(items)
                )
                return AccountSearchResponse(
                    query=query,
                    total=len(items),
                    results=items[:limit],
                )

    def list_accounts(
        self, query: Optional[ListAccountsQuery] = None
    ) -> AccountsPaginatedResponse:
        q = query or ListAccountsQuery()
        tier_val: Optional[str] = (
            q.priority_tier.value
            if isinstance(q.priority_tier, PriorityTier)
            else q.priority_tier
        )
        with self.context.logger.span(
            "accounts.list", skip=q.skip, limit=q.limit, priority_tier=tier_val
        ):
            stats = self.get_summary_stats()
            with self.context.get_connection() as conn:
                if tier_val and tier_val != "all":
                    tier_total = getattr(
                        stats,
                        tier_val.replace(
                            PriorityTier.TIER_1_CRITICAL.value, "critical_count"
                        )
                        .replace(PriorityTier.TIER_2_HIGH.value, "high_count")
                        .replace(PriorityTier.TIER_3_MEDIUM.value, "medium_count")
                        .replace(PriorityTier.TIER_4_LOW.value, "low_count"),
                        None,
                    )
                    keys, total = self.context.reader.get_accounts_by_priority_tier(
                        conn, tier_val, skip=q.skip, limit=q.limit, total=tier_total
                    )
                elif q.has_critical_signals:
                    keys, total = (
                        self.context.reader.get_accounts_with_critical_signals(
                            conn,
                            skip=q.skip,
                            limit=q.limit,
                            total=stats.accounts_with_critical_signals,
                        )
                    )
                else:
                    keys, total = self.context.reader.get_all_accounts(
                        conn, skip=q.skip, limit=q.limit, total=stats.total_accounts
                    )

                items = self.context.reader.load_accounts_summary_batch(conn, keys)
                return AccountsPaginatedResponse(
                    total=total,
                    skip=q.skip,
                    limit=q.limit,
                    items=items,
                )

    def get_accounts_by_signal(
        self, query: AccountsBySignalQuery
    ) -> AccountsBySignalResponse:
        with self.context.logger.span(
            "accounts.by_signal",
            signal=query.signal_name,
            skip=query.skip,
            limit=query.limit,
        ):
            with self.context.get_connection() as conn:
                keys, total = self.context.reader.get_accounts_by_signal(
                    conn, query.signal_name, skip=query.skip, limit=query.limit
                )
                items = self.context.reader.load_accounts_summary_batch(conn, keys)
                return AccountsBySignalResponse(
                    signal=query.signal_name,
                    total=total,
                    skip=query.skip,
                    limit=query.limit,
                    items=items,
                )

    def get_summary_stats(self) -> SummaryStats:
        with self.context.logger.span("accounts.summary_stats"):
            with self.context.get_connection() as conn:
                raw_stats = self.context.reader.get_summary_stats(conn)
                return SummaryStats(**raw_stats)

    def save_account(
        self, account: Union[Account, InsertAccountCommand]
    ) -> SaveAccountResponse:
        if isinstance(account, InsertAccountCommand):
            target_account = account.account
            target_tier = account.priority_tier or self.compute_priority_tier(
                target_account
            )
        else:
            target_account = account
            target_tier = self.compute_priority_tier(target_account)

        tier_str: str = (
            target_tier.value
            if isinstance(target_tier, PriorityTier)
            else target_tier
        )

        with self.context.logger.span(
            "accounts.save", account_key=target_account.account_key, tier=tier_str
        ):
            with self.context.get_connection() as conn:
                acc_id = self.context.writer.insert_account(
                    conn, target_account, tier_str
                )
                conn.commit()
                self.context.logger.info(
                    "Account saved successfully",
                    account_id=acc_id,
                    account_key=target_account.account_key,
                    tier=tier_str,
                )
                return SaveAccountResponse(
                    account_id=acc_id,
                    account_key=target_account.account_key,
                    priority_tier=target_tier,
                )

    def delete_account(self, account_key: str) -> DeleteAccountResponse:
        with self.context.logger.span("accounts.delete", account_key=account_key):
            with self.context.get_connection() as conn:
                res = self.context.writer.delete_account(conn, account_key)
                conn.commit()
                return DeleteAccountResponse(success=res, account_key=account_key)

    def clear_all(self) -> ClearAccountsResponse:
        with self.context.logger.span("accounts.clear_all"):
            with self.context.get_connection() as conn:
                self.context.writer.clear_accounts(conn)
                conn.commit()
                self.context.logger.info("All accounts cleared")
                return ClearAccountsResponse(
                    success=True, message="All accounts cleared"
                )
