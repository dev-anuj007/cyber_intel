import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from sqlmodel import col, func, select

from src.services.database.dependencies import default_database_service
from src.services.database.database_service import DatabaseService
from src.services.jobs.internals.repositories.models import BackgroundJobTable
from src.services.jobs.types import (
    JobDetail,
    JobListQuery,
    JobStatus,
    JobSummary,
)


class JobsReader:
    def __init__(self, db_path: Optional[Any] = None) -> None:
        self._db = DatabaseService(db_path=db_path) if db_path is not None else default_database_service

    def get_job(self, job_id: str) -> Optional[JobDetail]:
        with self._db.get_session() as session:
            row = session.exec(select(BackgroundJobTable).where(col(BackgroundJobTable.job_id) == job_id)).first()
            return self._map_detail(row) if row else None

    def list_jobs(self, query: JobListQuery = JobListQuery()) -> Tuple[List[JobSummary], int]:
        with self._db.get_session() as session:
            stmt = select(BackgroundJobTable)
            count_stmt = select(func.count()).select_from(BackgroundJobTable)
            if query.job_type:
                stmt = stmt.where(col(BackgroundJobTable.job_type) == query.job_type)
                count_stmt = count_stmt.where(col(BackgroundJobTable.job_type) == query.job_type)
            if query.status:
                stmt = stmt.where(col(BackgroundJobTable.status) == query.status)
                count_stmt = count_stmt.where(col(BackgroundJobTable.status) == query.status)
            total = session.exec(count_stmt).one()
            rows = session.exec(
                stmt.order_by(col(BackgroundJobTable.id).desc()).offset(query.skip).limit(query.limit)
            ).all()
            return [self._map_summary(r) for r in rows], total

    def _map_detail(self, row: BackgroundJobTable) -> JobDetail:
        base = self._base(row)
        base["progress_percent"] = self._progress_percent(row.progress_current, row.progress_total, row.status)
        base["duration_ms"] = self._duration_ms(row.started_at, row.completed_at)
        base["payload"] = self._load_json(row.payload_json, {})
        base["results"] = self._load_json(row.results_json, None)
        base["metadata"] = self._load_json(row.metadata_json, {})
        return JobDetail(**base)

    def _map_summary(self, row: BackgroundJobTable) -> JobSummary:
        base = self._base(row)
        base["progress_percent"] = self._progress_percent(row.progress_current, row.progress_total, row.status)
        base["duration_ms"] = self._duration_ms(row.started_at, row.completed_at)
        base["metadata"] = self._load_json(row.metadata_json, {})
        return JobSummary(**base)

    def _base(self, row: BackgroundJobTable) -> Dict[str, Any]:
        return {
            "job_id": row.job_id,
            "job_type": row.job_type,
            "title": row.title,
            "user_id": row.user_id,
            "status": JobStatus(row.status) if row.status in JobStatus.__members__.values() else row.status,
            "progress_current": row.progress_current,
            "progress_total": row.progress_total,
            "retry_count": row.retry_count,
            "max_retries": row.max_retries,
            "payload_json": row.payload_json,
            "results_json": row.results_json,
            "metadata_json": row.metadata_json,
            "error_message": row.error_message,
            "trace_id": row.trace_id,
            "created_at": self._format_datetime(row.created_at),
            "started_at": self._format_datetime(row.started_at),
            "completed_at": self._format_datetime(row.completed_at),
        }

    def _format_datetime(self, val: Optional[Union[datetime, str]]) -> Optional[str]:
        if val is None:
            return None
        if isinstance(val, datetime):
            return val.isoformat()
        return str(val)

    def _progress_percent(self, current: int, total: int, status: str) -> int:
        return 100 if status == "completed" else min(100, int((current / max(1, total)) * 100))

    def _duration_ms(
        self,
        started_at: Optional[Union[datetime, str]],
        completed_at: Optional[Union[datetime, str]],
    ) -> Optional[int]:
        if not started_at or not completed_at:
            return None
        try:
            t0 = (
                started_at
                if isinstance(started_at, datetime)
                else datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
            )
            t1 = (
                completed_at
                if isinstance(completed_at, datetime)
                else datetime.fromisoformat(str(completed_at).replace("Z", "+00:00"))
            )
            return int((t1 - t0).total_seconds() * 1000)
        except Exception:
            return None

    def _load_json(self, value: Optional[str], default: Any) -> Any:
        try:
            return json.loads(value) if value is not None else default
        except Exception:
            return default
