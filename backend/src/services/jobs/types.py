from enum import Enum
from typing import Any, Callable, Dict, List, Optional

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


class JobListQuery(BaseModel):
    skip: int = 0
    limit: int = 20
    job_type: Optional[str] = None
    status: Optional[str] = None


class SubmitJobCommand(BaseModel):
    job_type: str
    title: str = "Background Job"
    payload: Dict[str, Any] = {}
    progress_total: int = 1
    user_id: Optional[int] = None
    max_retries: int = 3
    trace_id: Optional[str] = None
    auto_start: bool = True


class CreateJobRequest(BaseModel):
    job_type: str
    title: Optional[str] = None
    description: Optional[str] = None
    payload: Dict[str, Any] = {}
    progress_total: int = 100
    user_id: Optional[int] = None
    max_retries: int = 3
    auto_start: bool = False


class CreateJobCommand(BaseModel):
    job_id: str
    job_type: str = "general"
    title: str = ""
    payload: Dict[str, Any] = {}
    progress_total: int = 1
    user_id: Optional[Any] = None
    max_retries: int = 3
    trace_id: Optional[str] = None


class UpdateProgressCommand(BaseModel):
    job_id: str
    current: int
    total: int
    metadata: Optional[Dict[str, Any]] = None
    partial_results: Optional[Any] = None


class CompleteJobCommand(BaseModel):
    job_id: str
    results: Optional[Any] = None
    metadata: Optional[Dict[str, Any]] = None


class JobHandlerResult(BaseModel):
    results: Optional[Any] = None
    metadata: Optional[Dict[str, Any]] = None


ProgressCallback = Callable[[int, int, Optional[Dict[str, Any]], Optional[Any]], None]
JobHandlerFunc = Callable[[str, Dict[str, Any], ProgressCallback], Any]
