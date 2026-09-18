from typing import Protocol, Optional, Dict, List, Tuple, Any, Union
from enum import Enum
import sqlite3
from pydantic import BaseModel, ConfigDict


class SignalSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SecuritySignal(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    name: str
    severity: SignalSeverity
    category: str
    evidence: str


class Asset(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    ip: Optional[str] = None
    port: Optional[int] = None
    hostname: Optional[str] = None


class Account(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    account_key: str
    domain: Optional[str] = None
    domains: List[str] = []
    priority_tier: Optional[str] = None
    critical_signals_count: int = 0
    high_signals_count: int = 0
    medium_signals_count: int = 0
    low_signals_count: int = 0
    total_signals_count: int = 0
    total_assets: int = 0
    total_subdomains: int = 0
    assets: List[Asset] = []
    ips: List[str] = []
    hostnames: List[str] = []
    ports: List[int] = []
    products: List[str] = []
    cloud_providers: List[str] = []
    signals: List[SecuritySignal] = []
    ai_score: Optional[int] = None
    latest_score: Optional[Any] = None



class SummaryStats(BaseModel):
    total_accounts: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    accounts_with_critical_signals: int


class IAccountReader(Protocol):
    """Account data reader contract."""

    def load_account(self, conn: sqlite3.Connection, account_key: str) -> Optional[Account]:
        ...

    def load_accounts_batch(self, conn: sqlite3.Connection, account_keys: List[str], as_dict: bool = False) -> List[Any]:
        ...

    def load_accounts_summary_batch(self, conn: sqlite3.Connection, account_keys: List[str]) -> List[Dict[str, Any]]:
        ...

    def search_accounts_by_domain(self, conn: sqlite3.Connection, domain_query: str, limit: int = 10) -> List[str]:
        ...

    def get_accounts_by_signal(self, conn: sqlite3.Connection, signal_name: str, skip: int = 0, limit: int = 20) -> Tuple[List[str], int]:
        ...

    def get_accounts_with_critical_signals(self, conn: sqlite3.Connection, skip: int = 0, limit: int = 20) -> Tuple[List[str], int]:
        ...

    def get_all_accounts(self, conn: sqlite3.Connection, skip: int = 0, limit: int = 20) -> Tuple[List[str], int]:
        ...

    def get_accounts_by_priority_tier(self, conn: sqlite3.Connection, priority_tier: str, skip: int = 0, limit: int = 20) -> Tuple[List[str], int]:
        ...

    def get_summary_stats(self, conn: sqlite3.Connection) -> Dict[str, int]:
        ...


class IAccountWriter(Protocol):
    """Account data writer contract."""

    def insert_account(self, conn: sqlite3.Connection, account: Account, priority_tier: str) -> int:
        ...

    def clear_accounts(self, conn: sqlite3.Connection) -> None:
        ...


class IAccountsService(Protocol):
    """Accounts business service contract."""

    def get_account(self, account_key: str) -> Optional[Account]:
        ...

    def get_accounts_batch(self, account_keys: List[str], as_dict: bool = False) -> List[Any]:
        ...

    def search_accounts(self, query: str, limit: int = 10) -> List[Any]:
        ...

    def list_accounts(
        self,
        skip: int = 0,
        limit: int = 20,
        priority_tier: Optional[str] = None,
        has_critical_signals: Optional[bool] = None,
    ) -> Tuple[List[Any], int]:
        ...

    def get_summary_stats(self, force_refresh: bool = False) -> Dict[str, int]:
        ...

    def save_account(self, account: Account) -> int:
        ...

    def compute_priority_tier(self, account: Account) -> str:
        ...
