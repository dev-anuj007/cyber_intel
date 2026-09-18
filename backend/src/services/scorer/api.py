import os
from typing import List, Optional
from fastapi import APIRouter, Depends

from src.core.exceptions import InvalidInputError, ExternalServiceError, RateLimitError, NotFoundError
from src.services.scorer.types import AccountScore, ScoringRequest, LLMStats
from src.services.scorer.scorer_service import ScorerService, default_scorer_service
from src.services.accounts.accounts_service import AccountsService, default_accounts_service
from src.services.auth.api import get_current_user_optional
from src.services.logger import get_logger

logger = get_logger("scorer.api")


router = APIRouter(tags=["AI Scoring & Inference"])


def get_accounts_service() -> AccountsService:
    return default_accounts_service


def get_user_scorer(
    current_user: Optional[dict] = Depends(get_current_user_optional),
) -> ScorerService:
    api_key = current_user.get("gemini_api_key") if current_user else None
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise InvalidInputError(
            message="Gemini API key not configured. Please open Profile settings and add your Google Gemini API key to run AI scoring.",
            code="MISSING_GEMINI_API_KEY",
        )
    return ScorerService(api_key=api_key)


@router.post("/api/score", response_model=AccountScore)
def score_account(
    request: ScoringRequest,
    scorer: ScorerService = Depends(get_user_scorer),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    try:
        target_account = request.account
        if not target_account:
            target_account = accounts_service.get_account(request.account_key)
            if not target_account:
                raise NotFoundError(
                    f"Account '{request.account_key}' not found in platform database", 
                    code="ACCOUNT_NOT_FOUND"
                )
        return scorer.score_account(target_account)
    except ValueError as e:
        raise InvalidInputError(message=str(e), code="INVALID_SCORING_INPUT")
    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "quota" in err_str.lower():
            raise RateLimitError(
                message="Gemini API rate limit or quota exceeded. Please try again in a few moments."
            )
        logger.error(f"Error scoring account: {e}")
        raise ExternalServiceError(
            message=f"AI Scoring service failure: {str(e)}", 
            code="SCORER_INFERENCE_FAILURE"
        )



@router.post("/api/score/batch", response_model=List[AccountScore])
def score_batch(
    account_keys: List[str],
    limit: int = 10,
    scorer: ScorerService = Depends(get_user_scorer),
):
    """Score multiple accounts in batch, honoring user-specific API key if configured."""
    return scorer.score_batch(account_keys=account_keys, limit=limit)


@router.get("/api/llm-stats", response_model=LLMStats)
def get_llm_stats():
    """Get aggregate LLM call statistics, tokens used, and costs."""
    summary = default_scorer_service.get_summary()
    return LLMStats(
        total_calls=summary["total_calls"],
        total_tokens=summary["total_tokens"],
        total_cost_usd=summary["total_cost_usd"],
        avg_latency_ms=summary["avg_latency_ms"],
        trace_file=summary["trace_file"],
    )
