import secrets
import time
from typing import Any, Dict, List, Optional, Tuple

from src.services.jobs.dependencies import (
    JobsServiceDependencyContext,
    get_jobs_dependency_context,
)
from src.services.jobs.internals.dispatchers import create_default_dispatcher
from src.services.jobs.protocols import (
    IJobDispatcher,
    IJobsReader,
    IJobsService,
    IJobsWriter,
)
from src.services.jobs.types import (
    CompleteJobCommand,
    CreateJobCommand,
    CreateJobRequest,
    JobDetail,
    JobHandlerFunc,
    JobHandlerResult,
    JobListQuery,
    JobStatus,
    JobSummary,
    SubmitJobCommand,
    UpdateProgressCommand,
)
from src.services.logger.context import get_current_trace_id, set_current_trace_id
from src.services.logger.logger_service import BaseLogger


class JobsService(IJobsService):
    def __init__(self, context: Optional[JobsServiceDependencyContext] = None):
        ctx = context or get_jobs_dependency_context()
        self._reader: IJobsReader = ctx.reader
        self._writer: IJobsWriter = ctx.writer
        self._logger: BaseLogger = ctx.logger
        self._dispatcher: IJobDispatcher = ctx.dispatcher or create_default_dispatcher(
            self.execute_job, logger=self._logger
        )
        self._handlers: Dict[str, JobHandlerFunc] = {}

    def register_handler(self, job_type: str, handler: JobHandlerFunc) -> None:
        self._handlers[job_type] = handler
        self._logger.info(f"Registered job handler for '{job_type}'", job_type=job_type)

    def submit_job(self, command: SubmitJobCommand) -> str:
        job_id = f"job_{command.job_type}_{int(time.time())}_{secrets.token_hex(4)}"
        active_trace_id = command.trace_id or get_current_trace_id()

        self._writer.create_job(
            CreateJobCommand(
                job_id=job_id,
                job_type=command.job_type,
                title=command.title,
                payload=command.payload,
                progress_total=command.progress_total,
                user_id=command.user_id,
                max_retries=command.max_retries,
                trace_id=active_trace_id,
            )
        )

        self._logger.info(
            "Background job queued",
            job_id=job_id,
            job_type=command.job_type,
            title=command.title,
            trace_id=active_trace_id,
        )

        if command.auto_start:
            self._dispatcher.dispatch(job_id, command.job_type)

        return job_id

    def create_job(self, request: CreateJobRequest) -> JobDetail:
        job_title = request.title or request.description or f"{request.job_type} Task"
        job_id = self.submit_job(
            SubmitJobCommand(
                job_type=request.job_type,
                title=job_title,
                payload=request.payload,
                progress_total=request.progress_total,
                user_id=request.user_id,
                max_retries=request.max_retries,
                auto_start=request.auto_start,
            )
        )
        result = self.get_job(job_id)
        if result is None:
            raise LookupError(f"Failed to load newly created job '{job_id}'")
        return result

    def update_job_progress(self, command: UpdateProgressCommand, status: Optional[Any] = None) -> None:
        if status:
            self._writer.update_status(job_id=command.job_id, status=getattr(status, "value", str(status)))
        self._writer.update_progress(command)

    def complete_job(self, command: CompleteJobCommand) -> None:
        self._writer.complete_job(command)

    def fail_job(self, job_id: str, error: str) -> None:
        self._writer.fail_job(job_id=job_id, error_message=error)

    def cancel_job(self, job_id: str) -> None:
        self._writer.update_status(job_id=job_id, status=JobStatus.CANCELLED)

    def execute_job(self, job_id: str) -> None:
        job = self._reader.get_job(job_id=job_id)
        if not job:
            self._logger.error("Job not found for execution", job_id=job_id)
            return

        if job.status == JobStatus.CANCELLED:
            self._logger.info("Job was cancelled before execution started", job_id=job_id)
            return

        self._writer.start_job(job_id=job_id)

        if job.trace_id:
            set_current_trace_id(job.trace_id)

        handler = self._handlers.get(job.job_type)
        if not handler:
            error_msg = f"No handler registered for job type '{job.job_type}'"
            self._logger.error(error_msg, job_id=job_id, job_type=job.job_type)
            self._writer.fail_job(job_id=job_id, error_message=error_msg)
            return

        with self._logger.span("jobs.execute", job_id=job_id, job_type=job.job_type):

            def progress_callback(
                current: int,
                total: int,
                metadata: Optional[Dict[str, Any]] = None,
                partial_results: Optional[Any] = None,
            ) -> None:
                updated = self._writer.update_progress(
                    UpdateProgressCommand(
                        job_id=job_id,
                        current=current,
                        total=total,
                        metadata=metadata,
                        partial_results=partial_results,
                    )
                )
                if not updated:
                    current_job = self._reader.get_job(job_id)
                    if current_job and current_job.status == JobStatus.CANCELLED:
                        raise InterruptedError(f"Job {job_id} cancelled by user")

            try:
                handler_result = self._parse_handler_result(handler(job_id, job.payload, progress_callback))
                latest_job = self._reader.get_job(job_id)
                if latest_job and latest_job.status == JobStatus.CANCELLED:
                    self._logger.info("Job was cancelled; skipping completion", job_id=job_id)
                    return

                self._writer.complete_job(
                    CompleteJobCommand(
                        job_id=job_id,
                        results=handler_result.results,
                        metadata=handler_result.metadata,
                    )
                )
                self._logger.info("Job executed successfully", job_id=job_id, job_type=job.job_type)
            except InterruptedError:
                self._logger.info("Job execution aborted due to cancellation", job_id=job_id)
            except Exception as exc:
                self._logger.exception(
                    f"Error executing job {job_id}: {exc}",
                    job_id=job_id,
                    job_type=job.job_type,
                )
                self._writer.fail_job(job_id=job_id, error_message=str(exc))

    def retry_job(self, job_id: str, auto_start: bool = True) -> str:
        job = self._reader.get_job(job_id=job_id)
        if not job:
            raise LookupError(f"Job '{job_id}' not found")
        self._writer.increment_retry(job_id=job_id)
        self._logger.info("Job queued for retry", job_id=job_id)
        if auto_start:
            self._dispatcher.dispatch(job_id, job.job_type)
        return job_id

    def get_job(self, job_id: str) -> Optional[JobDetail]:
        return self._reader.get_job(job_id=job_id)

    def list_jobs(self, query: JobListQuery = JobListQuery()) -> Tuple[List[JobSummary], int]:
        return self._reader.list_jobs(query=query)

    def recover_stale_jobs(self, stale_threshold_seconds: Optional[int] = None) -> int:
        count = self._writer.recover_stale_jobs(stale_threshold_seconds=stale_threshold_seconds)
        if count > 0:
            self._logger.info(
                f"Recovered {count} interrupted jobs to queued state",
                recovered_count=count,
            )
        return count

    def _parse_handler_result(self, raw: Any) -> JobHandlerResult:
        if isinstance(raw, dict) and "results" in raw:
            return JobHandlerResult(results=raw.get("results"), metadata=raw.get("metadata"))
        return JobHandlerResult(results=raw)
