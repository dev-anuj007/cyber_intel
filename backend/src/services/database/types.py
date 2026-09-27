from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


@dataclass
class DatabaseHealth:
    status: str
    engine: str
    storage_location: str
    size_bytes: int = 0
    tables: List[str] = field(default_factory=list)
    s3_direct_enabled: bool = False
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DatabaseStats:
    total_accounts: int = 0
    total_domains: int = 0
    total_signals: int = 0
    total_assets: int = 0
    total_scores: int = 0
    total_users: int = 0
    total_jobs: int = 0


@dataclass
class QueryRequest:
    sql: str
    params: List[Any] = field(default_factory=list)
    limit: int = 100


@dataclass
class QueryResponse:
    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    execution_time_ms: float


@dataclass
class DatabaseConfig:
    db_path: Optional[Union[Path, str]] = None
    database_url: Optional[str] = None
    pool_size: int = 20
    max_overflow: int = 10
    pool_pre_ping: bool = True
