from typing import Optional

from fastapi import APIRouter, Depends

from src.core.exceptions import (
    AuthenticationError,
    ExternalServiceError,
    InvalidInputError,
    NotFoundError,
)
from src.services.auth.api import get_current_user_optional
from src.services.eval.eval_service import EvalService, default_eval_service
from src.services.eval.eval_types import EvalCompareRequest, EvalRunRequest
from src.services.jobs.jobs_service import JobsService, default_jobs_service
from src.services.jobs.types import JobStatus, JobSubmitResponse
from src.services.logger import get_logger

logger = get_logger("eval.api")

router = APIRouter(prefix="/api/eval", tags=["Evaluation Harness & Benchmarks"])


def get_eval_service() -> EvalService:
    return default_eval_service


def get_jobs_service() -> JobsService:
    return default_jobs_service


@router.get("/prompts")
def list_eval_prompts(eval_service: EvalService = Depends(get_eval_service)):
    prompts = eval_service.list_prompts()
    return {"prompts": prompts}


@router.get("/dataset")
def get_eval_dataset(eval_service: EvalService = Depends(get_eval_service)):
    dataset = eval_service.get_default_dataset()
    return {"dataset": dataset, "total": len(dataset)}


@router.post("/run", response_model=JobSubmitResponse, status_code=202)
def execute_eval_run(
    req: EvalRunRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    eval_service: EvalService = Depends(get_eval_service),
    jobs_service: JobsService = Depends(get_jobs_service),
):
    if not req.dry_run:
        if not current_user:
            raise AuthenticationError(message="Authentication required. Please sign in to execute live AI evaluations.")
        user_api_key = current_user.get("gemini_api_key")
        if not user_api_key:
            raise InvalidInputError(
                message="Gemini API key not configured. Please open Profile settings and add your API key before running live evaluations.",
                code="MISSING_GEMINI_API_KEY",
            )
    else:
        user_api_key = current_user.get("gemini_api_key") if current_user else None

    user_id = current_user.get("id") if current_user else None
    sample_count = len(req.eval_set) if req.eval_set else (req.sample_limit or 25)
    title = f"Eval Harness ({req.prompt_version})" + (" [Dry Run]" if req.dry_run else " [Live]")

    payload = {
        "prompt_version": req.prompt_version,
        "custom_prompt_template": req.custom_prompt_template,
        "dry_run": req.dry_run,
        "api_key": user_api_key,
        "eval_set_path": req.eval_set_path,
        "eval_set": req.eval_set,
        "sample_limit": req.sample_limit,
    }

    job_id = jobs_service.submit_job(
        job_type="eval_run",
        title=title,
        payload=payload,
        progress_total=sample_count,
        user_id=user_id,
        max_retries=1,
        auto_start=True,
    )

    job_info = jobs_service.get_job(job_id)
    current_status = getattr(job_info, "status", JobStatus.QUEUED) if job_info else JobStatus.QUEUED

    return JobSubmitResponse(
        success=True,
        job_id=job_id,
        job_type="eval_run",
        status=current_status,
        message=f"Evaluation job processed successfully ({title})",
    )


@router.post("/compare", response_model=JobSubmitResponse, status_code=202)
def execute_eval_compare(
    req: EvalCompareRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    eval_service: EvalService = Depends(get_eval_service),
    jobs_service: JobsService = Depends(get_jobs_service),
):
    if not req.dry_run and not (req.file_a and req.file_b):
        if not current_user:
            raise AuthenticationError(
                message="Authentication required. Please sign in to execute live prompt comparisons."
            )
        user_api_key = current_user.get("gemini_api_key")
        if not user_api_key:
            raise InvalidInputError(
                message="Gemini API key not configured. Please open Profile settings and add your API key before running live comparisons.",
                code="MISSING_GEMINI_API_KEY",
            )
    else:
        user_api_key = current_user.get("gemini_api_key") if current_user else None

    user_id = current_user.get("id") if current_user else None
    single_count = len(req.eval_set) if req.eval_set else (req.sample_limit or 25)
    sample_count = 2 * single_count if not (req.file_a and req.file_b) else 2
    title = f"Eval Comparison ({req.prompt_a} vs {req.prompt_b})" + (" [Dry Run]" if req.dry_run else " [Live]")

    payload = {
        "prompt_a": req.prompt_a,
        "prompt_b": req.prompt_b,
        "custom_prompt_a": req.custom_prompt_a,
        "custom_prompt_b": req.custom_prompt_b,
        "dry_run": req.dry_run,
        "file_a": req.file_a,
        "file_b": req.file_b,
        "api_key": user_api_key,
        "eval_set_path": req.eval_set_path,
        "eval_set": req.eval_set,
        "sample_limit": req.sample_limit,
    }

    job_id = jobs_service.submit_job(
        job_type="eval_compare",
        title=title,
        payload=payload,
        progress_total=sample_count,
        user_id=user_id,
        max_retries=1,
        auto_start=True,
    )

    job_info = jobs_service.get_job(job_id)
    current_status = getattr(job_info, "status", JobStatus.QUEUED) if job_info else JobStatus.QUEUED

    return JobSubmitResponse(
        success=True,
        job_id=job_id,
        job_type="eval_compare",
        status=current_status,
        message=f"Prompt comparison job processed successfully ({title})",
    )


@router.get("/history")
def list_eval_history(eval_service: EvalService = Depends(get_eval_service)):
    history = eval_service.list_history()
    return {"history": history}


@router.get("/results/{filename}")
def get_eval_result_file(
    filename: str,
    eval_service: EvalService = Depends(get_eval_service),
):
    try:
        return eval_service.get_result_file(filename)
    except FileNotFoundError:
        raise NotFoundError(message="Eval result file not found", code="EVAL_RESULT_NOT_FOUND")
    except Exception as e:
        raise ExternalServiceError(message=f"Failed to read result file: {str(e)}", code="FILE_READ_ERROR")
