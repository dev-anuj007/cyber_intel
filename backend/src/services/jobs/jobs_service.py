import time
import secrets
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from contextlib import contextmanager
from src.services.database import get_db_connection, is_deployed
from src.services.jobs.types import (
    IJobsService,
    IJobsRepository,
    JobStatus,
    JobSummary,
    JobDetail,
    JobHandlerFunc,
)
from src.services.jobs.repositories.jobs_repository import JobsRepository
from src.services.jobs.repositories.dynamo_jobs import DynamoJobsRepository
from src.services.logger import get_logger, get_current_trace_id, set_current_trace_id

logger = get_logger("services.jobs")


class JobsService(IJobsService):
    def __init__(
        self,
        db_path: Optional[Path] = None,
        repository: Optional[IJobsRepository] = None,
    ):
        self.db_path = db_path
        if is_deployed() and repository is None:
            self.repository = DynamoJobsRepository()
        else:
            self.repository = repository or JobsRepository()
        self._handlers: Dict[str, JobHandlerFunc] = {}

    @contextmanager
    def _connection(self):
        if isinstance(self.repository, DynamoJobsRepository):
            yield None
        else:
            with get_db_connection(self.db_path) as conn:
                yield conn

    def register_handler(self, job_type: str, handler: JobHandlerFunc) -> None:
        self._handlers[job_type] = handler
        logger.info(f"Registered job handler for '{job_type}'", job_type=job_type)

    def submit_job(
        self,
        job_type: str,
        title: str,
        payload: Dict[str, Any],
        progress_total: int = 1,
        user_id: Optional[int] = None,
        max_retries: int = 3,
        trace_id: Optional[str] = None,
        auto_start: bool = True,
    ) -> str:
        job_id = f"job_{job_type}_{int(time.time())}_{secrets.token_hex(4)}"
        active_trace_id = trace_id or get_current_trace_id()

        with self._connection() as conn:
            self.repository.create_job(
                conn=conn,
                job_id=job_id,
                job_type=job_type,
                title=title,
                payload=payload,
                progress_total=progress_total,
                user_id=user_id,
                max_retries=max_retries,
                trace_id=active_trace_id,
            )
            if conn is not None:
                conn.commit()

        logger.info(
            "Background job queued",
            job_id=job_id,
            job_type=job_type,
            title=title,
            trace_id=active_trace_id,
        )

        if auto_start:
            threading.Thread(
                target=self.execute_job,
                args=(job_id,),
                daemon=True,
                name=f"Worker-{job_id}",
            ).start()

        return job_id

    def execute_job(self, job_id: str) -> None:
        with self._connection() as conn:
            job = self.repository.get_job(conn, job_id)
            if not job:
                logger.error("Job not found for execution", job_id=job_id)
                return

            self.repository.start_job(conn, job_id)
            if conn is not None:
                conn.commit()

        if job.get("trace_id"):
            set_current_trace_id(job["trace_id"])

        job_type = job["job_type"]
        handler = self._handlers.get(job_type)

        if not handler:
            error_msg = f"No handler registered for job type '{job_type}'"
            logger.error(error_msg, job_id=job_id, job_type=job_type)
            with self._connection() as conn:
                self.repository.fail_job(conn, job_id, error_msg)
                if conn is not None:
                    conn.commit()
            return

        with logger.span("jobs.execute", job_id=job_id, job_type=job_type):
            def progress_callback(
                current: int,
                total: int,
                metadata: Optional[Dict[str, Any]] = None,
                partial_results: Optional[Any] = None,
            ):
                with self._connection() as conn:
                    self.repository.update_progress(
                        conn=conn,
                        job_id=job_id,
                        current=current,
                        total=total,
                        metadata=metadata,
                        partial_results=partial_results,
                    )
                    if conn is not None:
                        conn.commit()

            try:
                result_payload = handler(job_id, job.get("payload", {}), progress_callback)
                
                results = result_payload
                metadata = None
                if isinstance(result_payload, dict) and "results" in result_payload:
                    results = result_payload.get("results")
                    metadata = result_payload.get("metadata")

                with self._connection() as conn:
                    self.repository.complete_job(
                        conn=conn,
                        job_id=job_id,
                        results=results,
                        metadata=metadata,
                    )
                    if conn is not None:
                        conn.commit()

                logger.info("Job executed successfully", job_id=job_id, job_type=job_type)

            except Exception as exc:
                logger.exception(f"Error executing job {job_id}: {exc}", job_id=job_id, job_type=job_type)
                with self._connection() as conn:
                    self.repository.fail_job(conn, job_id, str(exc))
                    if conn is not None:
                        conn.commit()

    def get_job(self, job_id: str) -> Optional[JobDetail]:
        with self._connection() as conn:
            data = self.repository.get_job(conn, job_id)
            if not data:
                return None
            return JobDetail(**data)

    def list_jobs(
        self,
        skip: int = 0,
        limit: int = 20,
        job_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Tuple[List[JobSummary], int]:
        with self._connection() as conn:
            items_raw, total = self.repository.list_jobs(
                conn=conn,
                skip=skip,
                limit=limit,
                job_type=job_type,
                status=status,
            )
            summaries = [JobSummary(**item) for item in items_raw]
            return summaries, total

    def retry_job(self, job_id: str, auto_start: bool = True) -> str:
        with self._connection() as conn:
            job = self.repository.get_job(conn, job_id)
            if not job:
                raise LookupError(f"Job '{job_id}' not found")

            self.repository.increment_retry(conn, job_id)
            if conn is not None:
                conn.commit()

        logger.info("Job queued for retry", job_id=job_id)

        if auto_start:
            threading.Thread(
                target=self.execute_job,
                args=(job_id,),
                daemon=True,
                name=f"Worker-Retry-{job_id}",
            ).start()

        return job_id

    def recover_stale_jobs(self) -> int:
        with self._connection() as conn:
            count = self.repository.recover_stale_jobs(conn)
            if conn is not None:
                conn.commit()
            if count > 0:
                logger.info(f"Recovered {count} interrupted jobs to queued state", recovered_count=count)
            return count


default_jobs_service = JobsService()
