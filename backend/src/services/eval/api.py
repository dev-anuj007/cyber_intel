from typing import Optional
from fastapi import APIRouter, Depends

from src.core.exceptions import (
    AuthenticationError,
    InvalidInputError,
    NotFoundError,
    ExternalServiceError,
)
from src.services.eval.eval_types import EvalRunRequest, EvalCompareRequest
from src.services.eval.eval_service import EvalService, default_eval_service
from src.services.auth.api import get_current_user_optional
from src.services.logger import get_logger

logger = get_logger("eval.api")

router = APIRouter(prefix="/api/eval", tags=["Evaluation Harness & Benchmarks"])


def get_eval_service() -> EvalService:
    return default_eval_service


@router.get("/prompts")
def list_eval_prompts(eval_service: EvalService = Depends(get_eval_service)):
    prompts = eval_service.list_prompts()
    return {"prompts": prompts}


@router.get("/dataset")
def get_eval_dataset(eval_service: EvalService = Depends(get_eval_service)):
    dataset = eval_service.get_default_dataset()
    return {"dataset": dataset, "total": len(dataset)}


@router.post("/run")
def execute_eval_run(
    req: EvalRunRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    eval_service: EvalService = Depends(get_eval_service),
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

    try:
        return eval_service.run_eval(
            prompt_version=req.prompt_version,
            custom_prompt_template=req.custom_prompt_template,
            dry_run=req.dry_run,
            api_key=user_api_key,
            eval_set_path=req.eval_set_path,
            eval_set=req.eval_set,
            sample_limit=req.sample_limit,
        )
    except ValueError as e:
        raise InvalidInputError(message=str(e), code="INVALID_EVAL_INPUT")
    except Exception as e:
        logger.error(f"Eval run error: {e}", exc_info=True)
        raise ExternalServiceError(message=f"Eval harness execution failed: {str(e)}", code="EVAL_RUN_FAILURE")


@router.post("/compare")
def execute_eval_compare(
    req: EvalCompareRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    eval_service: EvalService = Depends(get_eval_service),
):
    if not req.dry_run and not (req.file_a and req.file_b):
        if not current_user:
            raise AuthenticationError(message="Authentication required. Please sign in to execute live prompt comparisons.")
        user_api_key = current_user.get("gemini_api_key")
        if not user_api_key:
            raise InvalidInputError(
                message="Gemini API key not configured. Please open Profile settings and add your API key before running live comparisons.",
                code="MISSING_GEMINI_API_KEY",
            )
    else:
        user_api_key = current_user.get("gemini_api_key") if current_user else None

    try:
        return eval_service.compare_prompts(
            prompt_a=req.prompt_a,
            prompt_b=req.prompt_b,
            custom_prompt_a=req.custom_prompt_a,
            custom_prompt_b=req.custom_prompt_b,
            dry_run=req.dry_run,
            file_a=req.file_a,
            file_b=req.file_b,
            api_key=user_api_key,
            eval_set_path=req.eval_set_path,
            eval_set=req.eval_set,
            sample_limit=req.sample_limit,
        )
    except FileNotFoundError as e:
        raise NotFoundError(message=str(e), code="EVAL_FILE_NOT_FOUND")
    except ValueError as e:
        raise InvalidInputError(message=str(e), code="INVALID_COMPARISON_INPUT")
    except Exception as e:
        logger.error(f"Eval comparison error: {e}", exc_info=True)
        raise ExternalServiceError(message=f"Eval comparison failed: {str(e)}", code="EVAL_COMPARE_FAILURE")


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

