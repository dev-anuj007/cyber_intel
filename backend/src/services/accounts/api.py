from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends

from src.core.exceptions import ExternalServiceError, NotFoundError
from src.services.accounts.dependencies import get_accounts_service
from src.services.accounts.protocols import IAccountsService
from src.services.accounts.types import (
    Account,
    AccountsBySignalQuery,
    AccountsBySignalResponse,
    AccountScoreHistoryResponse,
    AccountSearchResponse,
    AccountsHealthResponse,
    AccountsPaginatedResponse,
    AccountVersionsResponse,
    DeleteAccountResponse,
    ListAccountsQuery,
    SummaryStats,
)
from src.services.logger.logger_service import get_logger
from src.services.scorer.dependencies import get_scorer_service
from src.services.scorer.protocols import IScorerService
from src.services.scorer.types import ScoreHistoryItem

logger = get_logger("services.accounts.api")
router = APIRouter(tags=["Accounts & Prospecting"])


@router.get("/api/accounts/summary", response_model=SummaryStats)
def get_summary(
    accounts_service: IAccountsService = Depends(get_accounts_service),
) -> SummaryStats:
    stats = accounts_service.get_summary_stats()
    if stats.total_accounts == 0:
        raise ExternalServiceError(
            message="No accounts in database", code="NO_ACCOUNTS_IN_DB", status_code=503
        )
    return stats


@router.get("/api/accounts/search", response_model=AccountSearchResponse)
def search_accounts(
    q: str = "",
    limit: int = 10,
    accounts_service: IAccountsService = Depends(get_accounts_service),
) -> AccountSearchResponse:
    effective_limit = min(max(1, limit), 10)
    return accounts_service.search_accounts(q, limit=effective_limit)


@router.get(
    "/api/accounts/signal/{signal_name}", response_model=AccountsBySignalResponse
)
def get_accounts_by_signal_endpoint(
    signal_name: str,
    skip: int = 0,
    limit: int = 20,
    accounts_service: IAccountsService = Depends(get_accounts_service),
) -> AccountsBySignalResponse:
    query = AccountsBySignalQuery(signal_name=signal_name, skip=skip, limit=limit)
    return accounts_service.get_accounts_by_signal(query)


@router.get("/api/accounts", response_model=AccountsPaginatedResponse)
def list_accounts(
    skip: int = 0,
    limit: int = 20,
    priority_tier: Optional[str] = None,
    has_critical_signals: Optional[bool] = None,
    accounts_service: IAccountsService = Depends(get_accounts_service),
) -> AccountsPaginatedResponse:
    query = ListAccountsQuery(
        skip=skip,
        limit=limit,
        priority_tier=priority_tier,
        has_critical_signals=has_critical_signals,
    )
    return accounts_service.list_accounts(query)


@router.get(
    "/api/accounts/{account_key}/score-history",
    response_model=AccountScoreHistoryResponse,
)
def get_account_score_history(
    account_key: str,
    version: Optional[str] = None,
    scorer_service: IScorerService = Depends(get_scorer_service),
) -> AccountScoreHistoryResponse:
    try:
        history: List[ScoreHistoryItem] = scorer_service.get_score_history(
            account_key, version=version
        )
    except Exception as e:
        logger.error(
            "Error fetching score history for account",
            account_key=account_key,
            error=str(e),
        )
        history = []
    return AccountScoreHistoryResponse(
        account_key=account_key,
        version=version,
        total_versions=len(history),
        history=history,
    )


@router.get("/api/accounts/health", response_model=AccountsHealthResponse)
def accounts_health(
    accounts_service: IAccountsService = Depends(get_accounts_service),
) -> AccountsHealthResponse:
    stats = accounts_service.get_summary_stats()
    return AccountsHealthResponse(
        status="healthy",
        service="accounts",
        total_accounts=stats.total_accounts,
    )


@router.get(
    "/api/accounts/{account_key}/versions", response_model=AccountVersionsResponse
)
def get_account_versions(
    account_key: str,
    accounts_service: IAccountsService = Depends(get_accounts_service),
) -> AccountVersionsResponse:
    return accounts_service.get_account_versions(account_key)


@router.get("/api/accounts/{account_key}", response_model=Account)
def get_account(
    account_key: str,
    version: Optional[str] = None,
    accounts_service: IAccountsService = Depends(get_accounts_service),
    scorer_service: IScorerService = Depends(get_scorer_service),
) -> Account:
    account = accounts_service.get_account(account_key, version=version)
    if not account:
        raise NotFoundError(
            message=f"Account '{account_key}' not found", code="ACCOUNT_NOT_FOUND"
        )

    if not account.latest_score and scorer_service is not None:
        try:
            account.latest_score = scorer_service.get_latest_score(
                account.account_key, version=version
            )
        except Exception:
            pass
    return account


@router.delete("/api/accounts/{account_key}", response_model=DeleteAccountResponse)
def delete_account(
    account_key: str,
    accounts_service: IAccountsService = Depends(get_accounts_service),
) -> DeleteAccountResponse:
    return accounts_service.delete_account(account_key)
