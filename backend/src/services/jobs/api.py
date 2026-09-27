from typing import Optional

from fastapi import APIRouter, Depends

from src.core.exceptions import InvalidInputError, NotFoundError
from src.services.auth.dependencies import get_current_user_optional
from src.services.jobs.dependencies import get_jobs_service
from src.services.jobs.protocols import IJobsService
from src.services.jobs.types import (
    JobDetail,
    JobListQuery,
    JobListResponse,
    JobStatus,
    JobSubmitRequest,
    JobSubmitResponse,
    SubmitJobCommand,
)

router = APIRouter(prefix="/api/jobs", tags=["Background Jobs"])


@router.post("", response_model=JobSubmitResponse, status_code=200)
@router.post("/", response_model=JobSubmitResponse, status_code=200)
@router.post("/submit", response_model=JobSubmitResponse, status_code=200)
def submit_job(
    req: JobSubmitRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    jobs_service: IJobsService = Depends(get_jobs_service),
):
    """Submit a generic asynchronous job to the background queue."""
    if not req.job_type or not req.job_type.strip():
        raise InvalidInputError("Job type is required", code="MISSING_JOB_TYPE")

    user_id = current_user.get("id") if current_user else None
    title = (req.title or "").strip() or f"{req.job_type.strip()} Task"

    job_id = jobs_service.submit_job(
        SubmitJobCommand(
            job_type=req.job_type.strip(),
            title=title,
            payload=req.payload,
            user_id=user_id,
            max_retries=req.max_retries,
            auto_start=True,
        )
    )

    return JobSubmitResponse(
        success=True,
        job_id=job_id,
        job_type=req.job_type.strip(),
        status=JobStatus.QUEUED,
        message="Background job queued successfully",
    )


@router.get("", response_model=JobListResponse)
def list_jobs(
    skip: int = 0,
    limit: int = 20,
    job_type: Optional[str] = None,
    status: Optional[str] = None,
    jobs_service: IJobsService = Depends(get_jobs_service),
):
    items, total = jobs_service.list_jobs(JobListQuery(skip=skip, limit=limit, job_type=job_type, status=status))
    return JobListResponse(total=total, skip=skip, limit=limit, items=items)


@router.get("/{job_id}", response_model=JobDetail)
def get_job(
    job_id: str,
    jobs_service: IJobsService = Depends(get_jobs_service),
):
    job = jobs_service.get_job(job_id)
    if not job:
        raise NotFoundError(f"Job '{job_id}' not found", code="JOB_NOT_FOUND")
    return job


@router.post("/{job_id}/retry", response_model=JobSubmitResponse)
def retry_job(
    job_id: str,
    jobs_service: IJobsService = Depends(get_jobs_service),
):
    try:
        retried_id = jobs_service.retry_job(job_id, auto_start=True)
        return JobSubmitResponse(
            success=True,
            job_id=retried_id,
            job_type="background_job",
            status=JobStatus.QUEUED,
            message="Job queued for retry",
        )
    except LookupError as e:
        raise NotFoundError(str(e), code="JOB_NOT_FOUND")


@router.post("/{job_id}/cancel")
def cancel_job(
    job_id: str,
    jobs_service: IJobsService = Depends(get_jobs_service),
):
    jobs_service.cancel_job(job_id)
    return {"success": True, "job_id": job_id, "status": "cancelled"}

