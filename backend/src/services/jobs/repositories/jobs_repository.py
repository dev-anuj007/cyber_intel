"""Jobs Data Repository with SQLModel ORM."""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlmodel import Session, col, func, select

from src.services.database import default_database_service
from src.services.database.database_service import DatabaseService
from src.services.jobs.repositories.models import BackgroundJobTable


class JobsRepository:
    def __init__(self, db_path: Optional[Any] = None, **kwargs: Any):
        self.db_path = db_path
        self._local_db_service = DatabaseService(db_path=db_path) if db_path is not None else None

    def _get_session(self, conn: Optional[Any] = None) -> Session:
        svc = self._local_db_service if self._local_db_service is not None else default_database_service
        return svc.get_session(conn)

    def create_job(
        self,
        conn: Optional[Any] = None,
        job_id: str = "",
        job_type: str = "general",
        title: str = "",
        payload: Optional[Dict[str, Any]] = None,
        progress_total: int = 1,
        user_id: Optional[Any] = None,
        max_retries: int = 3,
        trace_id: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        with self._get_session(conn) as session:
            job = BackgroundJobTable(
                job_id=job_id,
                job_type=job_type,
                title=title,
                user_id=int(user_id) if user_id is not None and str(user_id).isdigit() else None,
                status="queued",
                progress_current=0,
                progress_total=progress_total,
                retry_count=0,
                max_retries=max_retries,
                payload_json=json.dumps(payload or {}),
                results_json="null",
                metadata_json="{}",
                trace_id=trace_id,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            session.add(job)
            session.commit()
            return job_id

    def get_job(self, conn: Optional[Any] = None, job_id: str = "") -> Optional[Dict[str, Any]]:
        with self._get_session(conn) as session:
            statement = select(BackgroundJobTable).where(BackgroundJobTable.job_id == job_id)
            job = session.exec(statement).first()
            if not job:
                return None
            return self._map_model(job)

    def list_jobs(
        self,
        conn: Optional[Any] = None,
        skip: int = 0,
        limit: int = 20,
        job_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        with self._get_session(conn) as session:
            query = select(BackgroundJobTable)
            count_query = select(func.count()).select_from(BackgroundJobTable)

            if job_type:
                query = query.where(BackgroundJobTable.job_type == job_type)
                count_query = count_query.where(BackgroundJobTable.job_type == job_type)
            if status:
                query = query.where(BackgroundJobTable.status == status)
                count_query = count_query.where(BackgroundJobTable.status == status)

            total = session.exec(count_query).one() or 0

            query = (
                query.order_by(col(BackgroundJobTable.created_at).desc(), col(BackgroundJobTable.id).desc())
                .offset(skip)
                .limit(limit)
            )
            rows = session.exec(query).all()
            items = [self._map_model(r) for r in rows]
            return items, int(total)

    def start_job(self, conn: Optional[Any] = None, job_id: str = "") -> None:
        with self._get_session(conn) as session:
            job = session.exec(select(BackgroundJobTable).where(BackgroundJobTable.job_id == job_id)).first()
            if job:
                job.status = "running"
                if not job.started_at:
                    job.started_at = datetime.now(timezone.utc).isoformat()
                session.add(job)
                session.commit()

    def update_status(self, conn: Optional[Any] = None, job_id: str = "", status: Any = "") -> None:
        st_val = status.value if hasattr(status, "value") else str(status)
        with self._get_session(conn) as session:
            job = session.exec(select(BackgroundJobTable).where(BackgroundJobTable.job_id == job_id)).first()
            if job:
                job.status = st_val
                if st_val == "completed":
                    job.completed_at = datetime.now(timezone.utc).isoformat()
                session.add(job)
                session.commit()

    def update_progress(
        self,
        conn: Optional[Any] = None,
        job_id: str = "",
        current: int = 0,
        total: int = 1,
        metadata: Optional[Dict[str, Any]] = None,
        partial_results: Optional[Any] = None,
    ) -> None:
        with self._get_session(conn) as session:
            job = session.exec(select(BackgroundJobTable).where(BackgroundJobTable.job_id == job_id)).first()
            if job:
                job.progress_current = current
                job.progress_total = total
                if metadata is not None:
                    job.metadata_json = json.dumps(metadata)
                if partial_results is not None:
                    job.results_json = json.dumps(partial_results)
                session.add(job)
                session.commit()

    def complete_job(
        self,
        conn: Optional[Any] = None,
        job_id: str = "",
        results: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._get_session(conn) as session:
            job = session.exec(select(BackgroundJobTable).where(BackgroundJobTable.job_id == job_id)).first()
            if job:
                job.status = "completed"
                job.progress_current = job.progress_total
                job.results_json = json.dumps(results)
                if metadata is not None:
                    job.metadata_json = json.dumps(metadata)
                job.completed_at = datetime.now(timezone.utc).isoformat()
                session.add(job)
                session.commit()

    def fail_job(self, conn: Optional[Any] = None, job_id: str = "", error_message: str = "") -> None:
        with self._get_session(conn) as session:
            job = session.exec(select(BackgroundJobTable).where(BackgroundJobTable.job_id == job_id)).first()
            if job:
                job.status = "failed"
                job.error_message = error_message
                job.completed_at = datetime.now(timezone.utc).isoformat()
                session.add(job)
                session.commit()

    def increment_retry(self, conn: Optional[Any] = None, job_id: str = "") -> int:
        with self._get_session(conn) as session:
            job = session.exec(select(BackgroundJobTable).where(BackgroundJobTable.job_id == job_id)).first()
            if job:
                job.retry_count = (job.retry_count or 0) + 1
                job.status = "queued"
                job.error_message = None
                session.add(job)
                session.commit()
                return job.retry_count
            return 0

    def recover_stale_jobs(self, conn: Optional[Any] = None) -> int:
        with self._get_session(conn) as session:
            stale_jobs = session.exec(select(BackgroundJobTable).where(BackgroundJobTable.status == "running")).all()
            for job in stale_jobs:
                job.status = "queued"
                session.add(job)
            session.commit()
            return len(stale_jobs)

    def _map_model(self, job: BackgroundJobTable) -> Dict[str, Any]:
        d = {
            "id": job.id,
            "job_id": job.job_id,
            "job_type": job.job_type,
            "title": job.title,
            "user_id": job.user_id,
            "status": job.status,
            "progress_current": job.progress_current,
            "progress_total": job.progress_total,
            "retry_count": job.retry_count,
            "max_retries": job.max_retries,
            "payload_json": job.payload_json,
            "results_json": job.results_json,
            "metadata_json": job.metadata_json,
            "error_message": job.error_message,
            "trace_id": job.trace_id,
            "created_at": str(job.created_at) if job.created_at else None,
            "started_at": str(job.started_at) if job.started_at else None,
            "completed_at": str(job.completed_at) if job.completed_at else None,
        }

        try:
            d["payload"] = json.loads(d.get("payload_json") or "{}")
        except Exception:
            d["payload"] = {}

        try:
            d["results"] = json.loads(d.get("results_json") or "null")
        except Exception:
            d["results"] = None

        try:
            d["metadata"] = json.loads(d.get("metadata_json") or "{}")
        except Exception:
            d["metadata"] = {}

        current = d.get("progress_current", 0)
        total = max(1, d.get("progress_total", 1))
        d["progress_percent"] = min(100, int((current / total) * 100)) if d.get("status") != "completed" else 100

        duration_ms = None
        if d.get("started_at") and d.get("completed_at"):
            try:
                t0 = datetime.fromisoformat(str(d["started_at"]).replace("Z", "+00:00"))
                t1 = datetime.fromisoformat(str(d["completed_at"]).replace("Z", "+00:00"))
                duration_ms = int((t1 - t0).total_seconds() * 1000)
            except Exception:
                pass
        d["duration_ms"] = duration_ms

        return d
