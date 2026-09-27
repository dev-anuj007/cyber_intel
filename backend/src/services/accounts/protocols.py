from typing import Any, Dict, List, Optional, Protocol, Tuple, Union, runtime_checkable

from src.services.accounts.types import (
    Account,
    AccountsBatchQuery,
    AccountsBySignalQuery,
    AccountsBySignalResponse,
    AccountSearchResponse,
    AccountsPaginatedResponse,
    AccountVersionsResponse,
    AccountVersionSummary,
    ClearAccountsResponse,
    DeleteAccountResponse,
    InsertAccountCommand,
    ListAccountsQuery,
    PriorityTier,
    SaveAccountResponse,
    SummaryStats,
)


@runtime_checkable
class IAccountReader(Protocol):
    def load_account(
        self, conn: Any, account_key: str, version: Optional[str] = None
    ) -> Optional[Account]: ...

    def get_account_versions(
        self, conn: Any, account_key: str
    ) -> List[AccountVersionSummary]: ...

    def load_accounts_batch(
        self, conn: Any, account_keys: List[str], as_dict: bool = False
    ) -> List[Any]: ...

    def load_accounts_summary_batch(
        self, conn: Any, account_keys: List[str]
    ) -> List[Dict[str, Any]]: ...

    def search_accounts_by_domain(
        self, conn: Any, domain_query: str, limit: int = 10
    ) -> List[str]: ...

    def get_accounts_by_signal(
        self, conn: Any, signal_name: str, skip: int = 0, limit: int = 20
    ) -> Tuple[List[str], int]: ...

    def get_accounts_with_critical_signals(
        self, conn: Any, skip: int = 0, limit: int = 20, total: Optional[int] = None
    ) -> Tuple[List[str], int]: ...

    def get_all_accounts(
        self, conn: Any, skip: int = 0, limit: int = 20, total: Optional[int] = None
    ) -> Tuple[List[str], int]: ...

    def get_accounts_by_priority_tier(
        self,
        conn: Any,
        priority_tier: str,
        skip: int = 0,
        limit: int = 20,
        total: Optional[int] = None,
    ) -> Tuple[List[str], int]: ...

    def get_summary_stats(self, conn: Any) -> Dict[str, int]: ...


@runtime_checkable
class IAccountWriter(Protocol):
    def insert_account(
        self, conn: Any, account: Account, priority_tier: str
    ) -> int: ...

    def delete_account(self, conn: Any, account_key: str) -> bool: ...

    def clear_accounts(self, conn: Any) -> None: ...


@runtime_checkable
class IAccountsService(Protocol):
    def get_account(
        self, account_key: str, version: Optional[str] = None
    ) -> Optional[Account]: ...

    def get_account_versions(self, account_key: str) -> AccountVersionsResponse: ...

    def get_accounts_batch(
        self, account_keys: Union[List[str], AccountsBatchQuery], as_dict: bool = False
    ) -> List[Any]: ...

    def search_accounts(self, query: str, limit: int = 10) -> AccountSearchResponse: ...

    def list_accounts(
        self, query: Optional[ListAccountsQuery] = None
    ) -> AccountsPaginatedResponse: ...

    def get_accounts_by_signal(
        self, query: AccountsBySignalQuery
    ) -> AccountsBySignalResponse: ...

    def get_summary_stats(self) -> SummaryStats: ...

    def save_account(
        self, account: Union[Account, InsertAccountCommand]
    ) -> SaveAccountResponse: ...

    def compute_priority_tier(self, account: Account) -> PriorityTier: ...

    def delete_account(self, account_key: str) -> DeleteAccountResponse: ...

    def clear_all(self) -> ClearAccountsResponse: ...
