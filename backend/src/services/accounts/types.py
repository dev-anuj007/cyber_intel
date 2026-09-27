from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class SignalSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PriorityTier(str, Enum):
    TIER_1_CRITICAL = "tier_1_critical"
    TIER_2_HIGH = "tier_2_high"
    TIER_3_MEDIUM = "tier_3_medium"
    TIER_4_LOW = "tier_4_low"


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


class AccountVersionSummary(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    version: str
    account_key: str
    priority_tier: Optional[Union[PriorityTier, str]] = None
    signals_count: int = 0
    assets_count: int = 0
    ai_score: Optional[int] = None
    is_active: bool = False


class Account(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    account_key: str
    version: str = "v1"
    domain: Optional[str] = None
    domains: List[str] = Field(default_factory=list)
    priority_tier: Optional[Union[PriorityTier, str]] = None
    critical_signals_count: int = 0
    high_signals_count: int = 0
    medium_signals_count: int = 0
    low_signals_count: int = 0
    total_signals_count: int = 0
    total_assets: int = 0
    total_subdomains: int = 0
    assets: List[Asset] = Field(default_factory=list)
    ips: List[str] = Field(default_factory=list)
    hostnames: List[str] = Field(default_factory=list)
    ports: List[int] = Field(default_factory=list)
    products: List[str] = Field(default_factory=list)
    cloud_providers: List[str] = Field(default_factory=list)
    signals: List[SecuritySignal] = Field(default_factory=list)
    ai_score: Optional[int] = None
    latest_score: Optional[Any] = None
    available_versions: List[AccountVersionSummary] = Field(default_factory=list)


class SummaryStats(BaseModel):
    total_accounts: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    accounts_with_critical_signals: int


class ListAccountsQuery(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    skip: int = 0
    limit: int = 20
    priority_tier: Optional[Union[PriorityTier, str]] = None
    has_critical_signals: Optional[bool] = None
    search: Optional[str] = None


class InsertAccountCommand(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    account: Account
    priority_tier: Optional[Union[PriorityTier, str]] = None


class AccountsBatchQuery(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    account_keys: List[str]
    as_dict: bool = False


class AccountsBySignalQuery(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    signal_name: str
    skip: int = 0
    limit: int = 20


# --- API Response DTOs ---


class AccountSearchResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    query: str
    total: int
    results: List[Dict[str, Any]] = Field(default_factory=list)


class AccountsPaginatedResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    total: int
    skip: int
    limit: int
    items: List[Dict[str, Any]] = Field(default_factory=list)


class AccountsBySignalResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    signal: str
    total: int
    skip: int
    limit: int
    items: List[Dict[str, Any]] = Field(default_factory=list)


class AccountVersionsResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    account_key: str
    total_versions: int
    versions: List[AccountVersionSummary] = Field(default_factory=list)


class AccountScoreHistoryResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    account_key: str
    version: Optional[str] = None
    total_versions: int
    history: List[Dict[str, Any]] = Field(default_factory=list)


class AccountsHealthResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    status: str = "healthy"
    service: str = "accounts"
    total_accounts: int = 0


class SaveAccountResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    account_id: int
    account_key: str
    priority_tier: Optional[Union[PriorityTier, str]] = None


class DeleteAccountResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    success: bool
    account_key: str


class ClearAccountsResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    success: bool = True
    message: str = "All accounts cleared"
