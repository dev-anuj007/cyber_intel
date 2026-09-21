from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple

from pydantic import BaseModel


class JobStatus(str, Enum):
    QUEUED = "queued"
    PENDING = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobSubmitRequest(BaseModel):
    job_type: str
    title: str = "Background Job"
    payload: Dict[str, Any] = {}
    max_retries: int = 3


class JobSubmitResponse(BaseModel):
    success: bool
    job_id: str
    job_type: str
    status: JobStatus
    message: str
    trace_id: Optional[str] = None


class JobSummary(BaseModel):
    job_id: str
    job_type: str
    title: str
    status: JobStatus
    progress_current: int
    progress_total: int
    progress_percent: int
    retry_count: int
    max_retries: int
    metadata: Dict[str, Any]
    error_message: Optional[str] = None
    trace_id: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None


class JobDetail(BaseModel):
    job_id: str
    job_type: str
    title: str
    user_id: Optional[Any] = None
    status: JobStatus
    progress_current: int
    progress_total: int
    progress_percent: int
    retry_count: int
    max_retries: int
    payload: Dict[str, Any]
    results: Optional[Any] = None
    metadata: Dict[str, Any]
    error_message: Optional[str] = None
    trace_id: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None

    @property
    def progress(self) -> int:
        return self.progress_percent

    @property
    def result(self) -> Optional[Any]:
        return self.results

    @property
    def error(self) -> Optional[str]:
        return self.error_message


class JobListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    items: List[JobSummary]


ProgressCallback = Callable[[int, int, Optional[Dict[str, Any]], Optional[Any]], None]
JobHandlerFunc = Callable[[str, Dict[str, Any], ProgressCallback], Any]


class IJobsRepository(Protocol):
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
    ) -> str: ...

    def get_job(self, conn: Optional[Any], job_id: str) -> Optional[Dict[str, Any]]: ...

    def list_jobs(
        self,
        conn: Optional[Any],
        skip: int = 0,
        limit: int = 20,
        job_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]: ...

    def start_job(self, conn: Optional[Any], job_id: str) -> None: ...

    def update_status(self, conn: Optional[Any], job_id: str, status: Any) -> None: ...

    def update_progress(
        self,
        conn: Optional[Any],
        job_id: str,
        current: int,
        total: int,
        metadata: Optional[Dict[str, Any]] = None,
        partial_results: Optional[Any] = None,
    ) -> None: ...

    def complete_job(
        self,
        conn: Optional[Any],
        job_id: str,
        results: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None: ...

    def fail_job(self, conn: Optional[Any], job_id: str, error_message: str) -> None: ...

    def increment_retry(self, conn: Optional[Any], job_id: str) -> int: ...

    def recover_stale_jobs(self, conn: Optional[Any]) -> int: ...


class IJobsService(Protocol):
    def register_handler(self, job_type: str, handler: JobHandlerFunc) -> None: ...

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
    ) -> str: ...

    def execute_job(self, job_id: str) -> None: ...

    def get_job(self, job_id: str) -> Optional[JobDetail]: ...

    def list_jobs(
        self, skip: int = 0, limit: int = 20, job_type: Optional[str] = None, status: Optional[str] = None
    ) -> Tuple[List[JobSummary], int]: ...

    def retry_job(self, job_id: str) -> str: ...
