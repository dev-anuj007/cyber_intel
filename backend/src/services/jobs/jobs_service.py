import secrets
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from src.services.database import default_database_service, is_deployed
from src.services.database.database_service import DatabaseService
from src.services.jobs.repositories.jobs_repository import JobsRepository
from src.services.jobs.types import (
    IJobsRepository,
    IJobsService,
    JobDetail,
    JobHandlerFunc,
    JobStatus,
    JobSummary,
)
from src.services.logger import get_current_trace_id, get_logger, set_current_trace_id

logger = get_logger("services.jobs")


class JobsService(IJobsService):
    def __init__(
        self,
        db_path: Optional[Union[Path, str]] = None,
        repository: Optional[IJobsRepository] = None,
    ):
        self.db_path = Path(db_path) if isinstance(db_path, str) else db_path
        self._local_db_service = DatabaseService(db_path=self.db_path) if self.db_path is not None else None
        self.repository: IJobsRepository = repository or JobsRepository(db_path=self.db_path)
        self._handlers: Dict[str, JobHandlerFunc] = {}

    @contextmanager
    def _connection(self):
        svc = self._local_db_service if self._local_db_service is not None else default_database_service
        with svc.get_connection() as conn:
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
            if is_deployed():
                try:
                    import json
                    import os

                    import boto3

                    region = os.environ.get("AWS_REGION", "ap-south-1")
                    app_name = os.environ.get("APP_NAME", "sales-intel")
                    env = os.environ.get("ENVIRONMENT", "dev")

                    if job_type.startswith("eval"):
                        function_name = f"{app_name}-{env}-eval"
                    elif job_type.startswith("crawler"):
                        function_name = f"{app_name}-{env}-crawler"
                    elif job_type.startswith("scorer") or job_type.startswith("batch_score"):
                        function_name = f"{app_name}-{env}-scorer"
                    else:
                        function_name = f"{app_name}-{env}-jobs"

                    lambda_client = boto3.client("lambda", region_name=region)
                    lambda_client.invoke(
                        FunctionName=function_name,
                        InvocationType="Event",
                        Payload=json.dumps({"job_id": job_id, "action": "execute_job"}),
                    )
                    logger.info(
                        "Triggered asynchronous Lambda invocation for background job",
                        job_id=job_id,
                        function_name=function_name,
                    )
                except Exception as exc:
                    logger.warning(
                        f"Failed async Lambda invoke ({exc}), falling back to background thread",
                        job_id=job_id,
                        error=str(exc),
                    )
                    threading.Thread(
                        target=self.execute_job,
                        args=(job_id,),
                        daemon=True,
                        name=f"Worker-{job_id}",
                    ).start()
            else:
                threading.Thread(
                    target=self.execute_job,
                    args=(job_id,),
                    daemon=True,
                    name=f"Worker-{job_id}",
                ).start()

        return job_id

    def create_job(
        self,
        job_type: str,
        payload: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        title: Optional[str] = None,
        progress_total: int = 100,
        user_id: Optional[int] = None,
        max_retries: int = 3,
        auto_start: bool = False,
    ) -> JobDetail:
        job_title = title or description or f"{job_type} Task"
        job_id = self.submit_job(
            job_type=job_type,
            title=job_title,
            payload=payload or {},
            progress_total=progress_total,
            user_id=user_id,
            max_retries=max_retries,
            auto_start=auto_start,
        )
        res = self.get_job(job_id)
        if res is None:
            raise LookupError(f"Failed to load newly created job '{job_id}'")
        return res

    def update_job_progress(
        self,
        job_id: str,
        progress: int,
        status: Optional[Union[str, JobStatus]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        partial_results: Optional[Any] = None,
    ) -> None:
        with self._connection() as conn:
            if status:
                st_val = getattr(status, "value", str(status))
                self.repository.update_status(conn, job_id, st_val)
            self.repository.update_progress(
                conn=conn,
                job_id=job_id,
                current=progress,
                total=100,
                metadata=metadata,
                partial_results=partial_results,
            )
            if conn is not None:
                conn.commit()

    def complete_job(
        self,
        job_id: str,
        result: Optional[Any] = None,
        results: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        res = result if result is not None else results
        with self._connection() as conn:
            self.repository.complete_job(
                conn=conn,
                job_id=job_id,
                results=res,
                metadata=metadata,
            )
            if conn is not None:
                conn.commit()

    def fail_job(
        self,
        job_id: str,
        error: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        err = error or error_message or "Unknown error"
        with self._connection() as conn:
            self.repository.fail_job(conn, job_id, err)
            if conn is not None:
                conn.commit()

    def cancel_job(self, job_id: str) -> None:
        with self._connection() as conn:
            self.repository.update_status(conn, job_id, JobStatus.CANCELLED)
            if conn is not None:
                conn.commit()

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
