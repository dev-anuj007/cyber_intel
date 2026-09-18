from typing import Optional
from fastapi import APIRouter, Depends

from src.core.exceptions import NotFoundError, InvalidInputError
from src.services.jobs.types import (
    JobSubmitRequest,
    JobSubmitResponse,
    JobSummary,
    JobDetail,
    JobListResponse,
)
from src.services.jobs.jobs_service import JobsService, default_jobs_service
from src.services.auth.api import get_current_user_optional

router = APIRouter(prefix="/api/jobs", tags=["Background Jobs"])


def get_jobs_service() -> JobsService:
    return default_jobs_service


@router.post("/submit", response_model=JobSubmitResponse, status_code=202)
def submit_job(
    req: JobSubmitRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    jobs_service: JobsService = Depends(get_jobs_service),
):
    """Submit a generic asynchronous job to the background queue."""
    if not req.job_type or not req.job_type.strip():
        raise InvalidInputError("Job type is required", code="MISSING_JOB_TYPE")

    user_id = current_user.get("id") if current_user else None
    job_id = jobs_service.submit_job(
        job_type=req.job_type.strip(),
        title=req.title.strip() or f"{req.job_type.strip()} Task",
        payload=req.payload,
        user_id=user_id,
        max_retries=req.max_retries,
        auto_start=True,
    )

    return JobSubmitResponse(
        success=True,
        job_id=job_id,
        job_type=req.job_type.strip(),
        status="queued",
        message="Background job queued successfully",
    )


@router.get("", response_model=JobListResponse)
def list_jobs(
    skip: int = 0,
    limit: int = 20,
    job_type: Optional[str] = None,
    status: Optional[str] = None,
    jobs_service: JobsService = Depends(get_jobs_service),
):
    """List background jobs with optional filtering by type and status."""
    items, total = jobs_service.list_jobs(
        skip=skip,
        limit=limit,
        job_type=job_type,
        status=status,
    )
    return JobListResponse(
        total=total,
        skip=skip,
        limit=limit,
        items=items,
    )


@router.get("/{job_id}", response_model=JobDetail)
def get_job(
    job_id: str,
    jobs_service: JobsService = Depends(get_jobs_service),
):
    """Get full status and result payload for a background job."""
    job = jobs_service.get_job(job_id)
    if not job:
        raise NotFoundError(f"Job '{job_id}' not found", code="JOB_NOT_FOUND")
    return job


@router.post("/{job_id}/retry", response_model=JobSubmitResponse)
def retry_job(
    job_id: str,
    jobs_service: JobsService = Depends(get_jobs_service),
):
    """Retry a failed or stalled background job."""
    try:
        retried_id = jobs_service.retry_job(job_id, auto_start=True)
        return JobSubmitResponse(
            success=True,
            job_id=retried_id,
            job_type="background_job",
            status="queued",
            message="Job queued for retry",
        )
    except LookupError as e:
        raise NotFoundError(str(e), code="JOB_NOT_FOUND")
