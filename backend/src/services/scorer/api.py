from typing import List

from fastapi import APIRouter, Depends

from src.core.exceptions import ExternalServiceError, InvalidInputError, NotFoundError, RateLimitError
from src.services.accounts.protocols import IAccountsService
from src.services.accounts.dependencies import get_accounts_service
from src.services.logger.logger_service import get_logger
from src.services.scorer.dependencies import get_scorer_service, get_user_scorer
from src.services.scorer.protocols import IScorerService
from src.services.scorer.types import (
    AccountScore,
    BatchScoreCommand,
    LLMStats,
    ScoreAccountCommand,
    ScoringRequest,
)

logger = get_logger("scorer.api")

router = APIRouter(tags=["AI Scoring & Inference"])


@router.post("/api/score", response_model=AccountScore)
@router.post("/api/scorer/score", response_model=AccountScore)
def score_account(
    request: ScoringRequest,
    scorer: IScorerService = Depends(get_user_scorer),
    accounts_service: IAccountsService = Depends(get_accounts_service),
):
    try:
        target_account = request.account
        if not target_account:
            if not request.account_key:
                raise InvalidInputError("Either account or account_key must be provided", code="MISSING_ACCOUNT_INPUT")
            target_account = accounts_service.get_account(request.account_key)
            if not target_account:
                raise NotFoundError(
                    f"Account '{request.account_key}' not found in platform database", code="ACCOUNT_NOT_FOUND"
                )
        command = ScoreAccountCommand(
            account=target_account,
            prompt_version=getattr(request, "prompt_version", None),
        )
        return scorer.score_account(command)
    except ValueError as e:
        raise InvalidInputError(message=str(e), code="INVALID_SCORING_INPUT")
    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "quota" in err_str.lower():
            raise RateLimitError(message="Gemini API rate limit or quota exceeded. Please try again in a few moments.")
        logger.error(f"Error scoring account: {e}")
        raise ExternalServiceError(message=f"AI Scoring service failure: {str(e)}", code="SCORER_INFERENCE_FAILURE")


@router.get("/api/scorer/history/{account_key}")
@router.get("/api/scores/history/{account_key}")
def get_scorer_history_endpoint(
    account_key: str,
    scorer: IScorerService = Depends(get_user_scorer),
):
    return scorer.get_score_history(account_key)


@router.get("/api/scorer/latest/{account_key}")
@router.get("/api/scores/latest/{account_key}")
def get_scorer_latest_endpoint(
    account_key: str,
    scorer: IScorerService = Depends(get_user_scorer),
):
    latest = scorer.get_latest_score(account_key)
    if not latest:
        return {
            "account_key": account_key,
            "score": 0,
            "priority_tier": "tier_4_low",
            "version": 0,
            "key_risks": [],
            "suggested_outreach": "None",
            "score_rationale": "No score recorded yet",
        }
    return latest


@router.post("/api/score/batch", response_model=List[AccountScore])
def score_batch(
    account_keys: List[str],
    limit: int = 10,
    scorer: IScorerService = Depends(get_user_scorer),
):
    return scorer.score_batch(BatchScoreCommand(account_keys=account_keys, limit=limit))


@router.get("/api/llm-stats", response_model=LLMStats)
def get_llm_stats(scorer: IScorerService = Depends(get_scorer_service)):
    summary = scorer.get_summary()
    return LLMStats(
        total_calls=summary["total_calls"],
        total_tokens=summary["total_tokens"],
        total_cost_usd=summary["total_cost_usd"],
        avg_latency_ms=summary["avg_latency_ms"],
        trace_file=summary["trace_file"],
    )
