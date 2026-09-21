import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, Response

from src.core.exceptions import ExternalServiceError, NotFoundError
from src.services.accounts.accounts_service import AccountsService, default_accounts_service
from src.services.accounts.types import SummaryStats

router = APIRouter(tags=["Accounts & Prospecting"])


def get_accounts_service() -> AccountsService:
    return default_accounts_service


def get_scorer_service():
    from src.services.scorer.scorer_service import default_scorer_service

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
@router.get("/api/accounts/search/domain")
def search_accounts(
    q: str = "",
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
@router.get("/api/accounts/signal/{signal_name}")
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
    version: Optional[str] = None,
    scorer_service: Any = Depends(get_scorer_service),
):
    history = scorer_service.get_score_history_for_account(account_key, version=version)
    return {
        "account_key": account_key,
        "version": version,
        "total_versions": len(history),
        "history": history,
    }


@router.get("/api/accounts/health")
def accounts_health(accounts_service: AccountsService = Depends(get_accounts_service)):
    stats = accounts_service.get_summary_stats()
    return {"status": "healthy", "service": "accounts", "total_accounts": stats.get("total_accounts", 0)}


@router.get("/api/accounts/{account_key}/versions")
def get_account_versions(
    account_key: str,
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    versions = accounts_service.get_account_versions(account_key)
    return {
        "account_key": account_key,
        "total_versions": len(versions),
        "versions": [v.model_dump() if hasattr(v, "model_dump") else v for v in versions],
    }


@router.get("/api/accounts/{account_key}")
def get_account(
    account_key: str,
    version: Optional[str] = None,
    accounts_service: AccountsService = Depends(get_accounts_service),
    scorer_service: Any = Depends(get_scorer_service),
):
    account = accounts_service.get_account(account_key, version=version)
    if not account:
        raise NotFoundError(message=f"Account '{account_key}' not found", code="ACCOUNT_NOT_FOUND")

    acc_dict = account.model_dump() if hasattr(account, "model_dump") else account.dict()
    if not acc_dict.get("latest_score"):
        acc_dict["latest_score"] = scorer_service.get_latest_score_for_account(account.account_key)
    return acc_dict


@router.delete("/api/accounts/{account_key}")
def delete_account(
    account_key: str,
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    success = accounts_service.delete_account(account_key)
    return {"success": success, "account_key": account_key}
