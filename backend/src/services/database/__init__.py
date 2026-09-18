from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from src.services.database.types import (
    IDatabaseService,
    DatabaseHealth,
    DatabaseStats,
    QueryRequest,
    QueryResponse,
)
from src.services.database.database_service import DatabaseService
from src.services.database.dynamo import (
    is_deployed,
    get_dynamo_resource,
    get_dynamo_client,
    get_table_name,
    float_to_decimal,
    decimal_to_python,
)
from src.services.database.api import router as database_router, get_db_service
from src.services.database.s3_storage import S3DirectStorage

default_database_service = DatabaseService()


@contextmanager
def get_db_connection(db_path: Optional[Path] = None):
    if db_path is not None:
        service = DatabaseService(db_path=db_path)
        with service.get_connection() as conn:
            yield conn
    else:
        with default_database_service.get_connection() as conn:
            yield conn


def init_database(db_path: Optional[Path] = None) -> None:
    if db_path is not None:
        service = DatabaseService(db_path=db_path)
        service.init_schema()
    else:
        default_database_service.init_schema()


__all__ = [
    "IDatabaseService",
    "DatabaseHealth",
    "DatabaseStats",
    "QueryRequest",
    "QueryResponse",
    "DatabaseService",
    "default_database_service",
    "database_router",
    "get_db_service",
    "S3DirectStorage",
    "get_db_connection",
    "init_database",
    "is_deployed",
    "get_dynamo_resource",
    "get_dynamo_client",
    "get_table_name",
    "float_to_decimal",
    "decimal_to_python",
]
