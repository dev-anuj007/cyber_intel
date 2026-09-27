from typing import Any, ContextManager, Dict, List, Optional, Protocol, runtime_checkable
from sqlmodel import Session
from src.services.database.types import DatabaseHealth, DatabaseStats


@runtime_checkable
class IDatabaseConnectionContext(Protocol):
    def __enter__(self) -> Any:
        ...

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        ...

    def close(self) -> None:
        ...


@runtime_checkable
class IDatabaseSessionManager(Protocol):
    @property
    def is_postgres(self) -> bool:
        ...

    def get_raw_connection(self) -> Any:
        ...

    def get_connection(self) -> IDatabaseConnectionContext:
        ...

    def get_session(self, conn: Optional[Any] = None) -> Session:
        ...


@runtime_checkable
class IDatabaseReader(Protocol):
    def fetchone(self, sql: str, params: Optional[tuple] = None) -> Optional[Any]:
        ...

    def fetchall(self, sql: str, params: Optional[tuple] = None) -> List[Any]:
        ...

    def execute_query(self, sql: str, params: Optional[tuple] = None) -> List[Any]:
        ...

    def get_table_stats(self) -> Dict[str, int]:
        ...

    def get_health(self) -> DatabaseHealth:
        ...

    def get_stats(self) -> DatabaseStats:
        ...


@runtime_checkable
class IDatabaseWriter(Protocol):
    def execute(self, sql: str, params: Optional[tuple] = None) -> Any:
        ...

    def executemany(self, sql: str, params_list: List[tuple]) -> Any:
        ...

    def execute_update(self, sql: str, params: Optional[tuple] = None) -> Any:
        ...

    def execute_batch(self, sql: str, params_list: List[tuple]) -> Any:
        ...

    def init_schema(self) -> None:
        ...


@runtime_checkable
class IDatabaseService(Protocol):
    @property
    def is_postgres(self) -> bool:
        ...

    def get_connection(self) -> IDatabaseConnectionContext:
        ...

    def get_session(self, conn: Optional[Any] = None) -> Session:
        ...

    def execute(self, sql: str, params: Optional[tuple] = None) -> Any:
        ...

    def fetchone(self, sql: str, params: Optional[tuple] = None) -> Optional[Any]:
        ...

    def fetchall(self, sql: str, params: Optional[tuple] = None) -> List[Any]:
        ...

    def executemany(self, sql: str, params_list: List[tuple]) -> Any:
        ...

    def execute_query(self, sql: str, params: Optional[tuple] = None) -> List[Any]:
        ...

    def execute_update(self, sql: str, params: Optional[tuple] = None) -> Any:
        ...

    def execute_batch(self, sql: str, params_list: List[tuple]) -> Any:
        ...

    def get_table_stats(self) -> Dict[str, int]:
        ...

    def get_health(self) -> DatabaseHealth:
        ...

    def get_stats(self) -> DatabaseStats:
        ...

    def init_schema(self) -> None:
        ...

    def init_database(self) -> None:
        ...
