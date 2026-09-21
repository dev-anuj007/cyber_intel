"""Database Service Type Definitions and Interfaces."""

from dataclasses import dataclass, field
from typing import Any, ContextManager, Dict, List, Optional, Protocol


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


class IDatabaseService(Protocol):
    """Interface for the Database microservice."""

    def get_connection(self) -> ContextManager[Any]:
        """Context manager returning an active database connection."""
        ...

    def execute(self, sql: str, params: Optional[tuple] = None) -> Any:
        """Execute SQL query."""
        ...

    def fetchone(self, sql: str, params: Optional[tuple] = None) -> Optional[Any]:
        """Execute and fetch a single record."""
        ...

    def fetchall(self, sql: str, params: Optional[tuple] = None) -> List[Any]:
        """Execute and fetch all matching records."""
        ...

    def get_health(self) -> DatabaseHealth:
        """Inspect and return database health and status."""
        ...

    def get_stats(self) -> DatabaseStats:
        """Inspect and return core database entity counts."""
        ...

    def init_schema(self) -> None:
        """Initialize relational tables and indices."""
        ...

    def init_database(self) -> None:
        """Alias to initialize relational tables and indices."""
        ...

