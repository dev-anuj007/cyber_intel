import json
from typing import Optional
from fastapi import APIRouter, Response, Depends

from src.core.exceptions import NotFoundError, ExternalServiceError
from src.services.accounts.types import SummaryStats
from src.services.accounts.accounts_service import AccountsService, default_accounts_service
from src.services.scorer.scorer_service import ScorerService, default_scorer_service

router = APIRouter(tags=["Accounts & Prospecting"])


def get_accounts_service() -> AccountsService:
    return default_accounts_service


def get_scorer_service() -> ScorerService:
    return default_scorer_service


@router.get("/api/summary", response_model=SummaryStats)
@router.get("/api/accounts/summary", response_model=SummaryStats)
def get_summary(accounts_service: AccountsService = Depends(get_accounts_service)):
    stats = accounts_service.get_summary_stats()
    if stats["total_accounts"] == 0:
        raise ExternalServiceError(message="No accounts in database", code="NO_ACCOUNTS_IN_DB", status_code=503)
    return SummaryStats(**stats)


@router.get("/api/search")
@router.get("/api/accounts/search")
def search_accounts(
    q: str,
    limit: int = 10,
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    effective_limit = min(max(1, limit), 10)
    items = accounts_service.search_accounts(q, limit=effective_limit)
    payload = {
        "query": q,
        "total": len(items),
        "results": items[:effective_limit],
    }
    return Response(content=json.dumps(payload), media_type="application/json")


@router.get("/api/accounts/by-signal/{signal_name}")
def get_accounts_by_signal_endpoint(
    signal_name: str,
    skip: int = 0,
    limit: int = 20,
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    items, total = accounts_service.get_accounts_by_signal(signal_name, skip=skip, limit=limit)
    payload = {
        "signal": signal_name,
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": items,
    }
    return Response(content=json.dumps(payload), media_type="application/json")


@router.get("/api/accounts")
def list_accounts(
    skip: int = 0,
    limit: int = 20,
    priority_tier: Optional[str] = None,
    has_critical_signals: Optional[bool] = None,
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    items, total = accounts_service.list_accounts(
        skip=skip,
        limit=limit,
        priority_tier=priority_tier,
        has_critical_signals=has_critical_signals,
    )
    payload = {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": items,
    }
    return Response(content=json.dumps(payload), media_type="application/json")


@router.get("/api/accounts/{account_key}/score-history")
def get_account_score_history(
    account_key: str,
    scorer_service: ScorerService = Depends(get_scorer_service),
):
    history = scorer_service.get_score_history_for_account(account_key)
    return {
        "account_key": account_key,
        "total_versions": len(history),
        "history": history,
    }


@router.get("/api/accounts/{account_key}")
def get_account(
    account_key: str,
    accounts_service: AccountsService = Depends(get_accounts_service),
    scorer_service: ScorerService = Depends(get_scorer_service),
):
    account = accounts_service.get_account(account_key)
    if not account:
        raise NotFoundError(message=f"Account '{account_key}' not found", code="ACCOUNT_NOT_FOUND")

    acc_dict = account.model_dump() if hasattr(account, "model_dump") else account.dict()
    acc_dict["latest_score"] = scorer_service.get_latest_score_for_account(account_key)
    return acc_dict
