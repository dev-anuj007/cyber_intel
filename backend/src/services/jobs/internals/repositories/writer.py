import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlmodel import col, select

from src.services.database.dependencies import default_database_service
from src.services.database.database_service import DatabaseService
from src.services.jobs.internals.repositories.models import BackgroundJobTable
from src.services.jobs.types import (
    CompleteJobCommand,
    CreateJobCommand,
    UpdateProgressCommand,
)


class JobsWriter:
    def __init__(self, db_path: Optional[Any] = None) -> None:
        self._db = DatabaseService(db_path=db_path) if db_path is not None else default_database_service

    def create_job(self, command: CreateJobCommand) -> str:
        now = datetime.now(timezone.utc)
        with self._db.get_session() as session:
            session.add(
                BackgroundJobTable(
                    job_id=command.job_id,
                    job_type=command.job_type,
                    title=command.title,
                    user_id=(
                        int(command.user_id) if command.user_id is not None and str(command.user_id).isdigit() else None
                    ),
                    status="queued",
                    progress_current=0,
                    progress_total=command.progress_total,
                    retry_count=0,
                    max_retries=command.max_retries,
                    payload_json=json.dumps(command.payload),
                    results_json="null",
                    metadata_json="{}",
                    trace_id=command.trace_id,
                    created_at=now,
                )
            )
            session.commit()
        return command.job_id

    def start_job(self, job_id: str) -> bool:
        now = datetime.now(timezone.utc)
        with self._db.get_session() as session:
            job = session.exec(select(BackgroundJobTable).where(col(BackgroundJobTable.job_id) == job_id)).first()
            if job and job.status in ("queued", "pending"):
                job.status = "running"
                if not job.started_at:
                    job.started_at = now
                session.add(job)
                session.commit()
                return True
            return False

    def update_status(self, job_id: str, status: Any) -> None:
        st_val = status.value if hasattr(status, "value") else str(status)
        now = datetime.now(timezone.utc)
        with self._db.get_session() as session:
            job = session.exec(select(BackgroundJobTable).where(col(BackgroundJobTable.job_id) == job_id)).first()
            if job:
                job.status = st_val
                if st_val == "completed":
                    job.completed_at = now
                session.add(job)
                session.commit()

    def update_progress(self, command: UpdateProgressCommand) -> bool:
        with self._db.get_session() as session:
            job = session.exec(
                select(BackgroundJobTable).where(col(BackgroundJobTable.job_id) == command.job_id)
            ).first()
            if job:
                if job.status == "cancelled":
                    return False
                job.progress_current = command.current
                job.progress_total = command.total
                if command.metadata is not None:
                    job.metadata_json = json.dumps(command.metadata)
                if command.partial_results is not None:
                    job.results_json = json.dumps(command.partial_results)
                session.add(job)
                session.commit()
                return True
            return False

    def complete_job(self, command: CompleteJobCommand) -> bool:
        now = datetime.now(timezone.utc)
        with self._db.get_session() as session:
            job = session.exec(
                select(BackgroundJobTable).where(col(BackgroundJobTable.job_id) == command.job_id)
            ).first()
            if job:
                if job.status in ("cancelled", "failed"):
                    return False
                job.status = "completed"
                job.progress_current = job.progress_total
                job.results_json = json.dumps(command.results)
                if command.metadata is not None:
                    job.metadata_json = json.dumps(command.metadata)
                job.completed_at = now
                session.add(job)
                session.commit()
                return True
            return False

    def fail_job(self, job_id: str, error_message: str) -> bool:
        now = datetime.now(timezone.utc)
        with self._db.get_session() as session:
            job = session.exec(select(BackgroundJobTable).where(col(BackgroundJobTable.job_id) == job_id)).first()
            if job:
                if job.status == "cancelled":
                    return False
                job.status = "failed"
                job.error_message = error_message
                job.completed_at = now
                session.add(job)
                session.commit()
                return True
            return False

    def increment_retry(self, job_id: str) -> int:
        with self._db.get_session() as session:
            job = session.exec(select(BackgroundJobTable).where(col(BackgroundJobTable.job_id) == job_id)).first()
            if job:
                job.retry_count = (job.retry_count or 0) + 1
                job.status = "queued"
                job.error_message = None
                session.add(job)
                session.commit()
                return job.retry_count
        return 0

    def recover_stale_jobs(self, stale_threshold_seconds: Optional[int] = None) -> int:
        now = datetime.now(timezone.utc)
        with self._db.get_session() as session:
            stale_candidates = session.exec(
                select(BackgroundJobTable).where(col(BackgroundJobTable.status) == "running")
            ).all()

            recovered = []
            for job in stale_candidates:
                if stale_threshold_seconds is not None and stale_threshold_seconds > 0:
                    last_active = job.started_at or job.created_at
                    if last_active and (now - last_active.replace(tzinfo=timezone.utc if last_active.tzinfo is None else last_active.tzinfo)) < timedelta(seconds=stale_threshold_seconds):
                        continue
                job.status = "queued"
                session.add(job)
                recovered.append(job)

            session.commit()
            return len(recovered)
