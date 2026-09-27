import time
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.core.exceptions import DatabaseError, InvalidInputError
from src.services.database.dependencies import get_db_service
from src.services.database.protocols import IDatabaseService
from src.services.database.types import DatabaseHealth, DatabaseStats
from src.services.logger.logger_service import get_logger

logger = get_logger("services.database.api")

router = APIRouter(prefix="/api/database", tags=["Database Microservice"])


class QueryPayload(BaseModel):
    sql: str = Field(..., description="SQL SELECT statement to execute")
    params: List[Any] = Field(default_factory=list, description="Positional query parameters")
    limit: int = Field(default=100, ge=1, le=1000, description="Max rows to return")


class QueryResult(BaseModel):
    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    execution_time_ms: float


@router.get("/health", response_model=Dict[str, Any])
def database_health(db: IDatabaseService = Depends(get_db_service)):
    health: DatabaseHealth = db.get_health()
    return {
        "status": health.status,
        "engine": health.engine,
        "storage_location": health.storage_location,
        "size_bytes": health.size_bytes,
        "table_count": len(health.tables),
        "tables": health.tables,
        "s3_direct_enabled": health.s3_direct_enabled,
        "details": health.details,
    }


@router.get("/stats", response_model=Dict[str, int])
def database_stats(db: IDatabaseService = Depends(get_db_service)):
    stats: DatabaseStats = db.get_stats()
    return {
        "total_accounts": stats.total_accounts,
        "total_domains": stats.total_domains,
        "total_signals": stats.total_signals,
        "total_assets": stats.total_assets,
        "total_scores": stats.total_scores,
        "total_users": stats.total_users,
        "total_jobs": stats.total_jobs,
    }


@router.post("/query", response_model=QueryResult)
def execute_query(payload: QueryPayload, db: IDatabaseService = Depends(get_db_service)):
    normalized_sql = payload.sql.strip().lower()
    if (
        not normalized_sql.startswith("select")
        and not normalized_sql.startswith("pragma")
        and not normalized_sql.startswith("explain")
    ):
        raise InvalidInputError(
            message="Only read-only queries (SELECT, PRAGMA, EXPLAIN) are permitted through this API endpoint.",
            code="UNSUPPORTED_QUERY_TYPE",
        )

    start_time = time.perf_counter()
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(payload.sql, tuple(payload.params))
            col_names = [d[0] for d in cursor.description] if cursor.description else []
            rows = [list(r) for r in cursor.fetchmany(payload.limit)]
            elapsed = (time.perf_counter() - start_time) * 1000.0

            return QueryResult(
                columns=col_names,
                rows=rows,
                row_count=len(rows),
                execution_time_ms=round(elapsed, 2),
            )
    except Exception as e:
        logger.error(f"Database query error: {e}", sql=payload.sql)
        raise DatabaseError(message=f"Database query error: {str(e)}", code="DATABASE_QUERY_ERROR")

