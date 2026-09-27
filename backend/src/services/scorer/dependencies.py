import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Union

from fastapi import Depends

from src.core.exceptions import InvalidInputError
from src.services.accounts.protocols import IAccountsService
from src.services.accounts.types import Account
from src.services.auth.dependencies import get_current_user_optional
from src.services.database.database_service import DatabaseService
from src.services.database.dependencies import default_database_service
from src.services.database.protocols import IDatabaseService
from src.services.logger.logger_service import BaseLogger, get_logger
from src.services.prompts.protocols import IPromptService
from src.services.scorer.internals.repositories.reader import ScoreReader
from src.services.scorer.internals.repositories.writer import ScoreWriter
from src.services.scorer.protocols import IScoreReader, IScorerService, IScoreWriter
from src.services.scorer.types import (
    AccountScore,
    BatchScoreCommand,
    GetPromptQuery,
    LatestScoreResponse,
    LLMStats,
    ScoreAccountCommand,
    ScoreHistoryItem,
)


@dataclass(frozen=True)
class ScorerServiceDependencyContext:
    reader: IScoreReader
    writer: IScoreWriter
    db_service: IDatabaseService
    logger: BaseLogger
    accounts_service: Optional[IAccountsService] = None
    db_path: Optional[Union[Path, str]] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    prompt_version: Optional[str] = None
    prompt_service: Optional[IPromptService] = None


def get_scorer_dependency_context(
    db_path: Optional[Union[Path, str]] = None,
    reader: Optional[IScoreReader] = None,
    writer: Optional[IScoreWriter] = None,
    db_service: Optional[IDatabaseService] = None,
    logger: Optional[BaseLogger] = None,
    accounts_service: Optional[IAccountsService] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    prompt_version: Optional[str] = None,
    prompt_service: Optional[IPromptService] = None,
) -> ScorerServiceDependencyContext:
    resolved_db_service: IDatabaseService = db_service or (
        DatabaseService(db_path=Path(db_path))
        if db_path is not None
        else default_database_service
    )
    return ScorerServiceDependencyContext(
        reader=reader if reader is not None else ScoreReader(),
        writer=writer if writer is not None else ScoreWriter(),
        db_service=resolved_db_service,
        logger=logger or get_logger("services.scorer"),
        accounts_service=accounts_service,
        db_path=db_path,
        api_key=api_key,
        model=model,
        prompt_version=prompt_version,
        prompt_service=prompt_service,
    )


def create_scorer_service(
    context: Optional[ScorerServiceDependencyContext] = None,
    **kwargs: Any,
) -> IScorerService:
    from src.services.scorer.scorer_service import ScorerService

    if context is None:
        context = get_scorer_dependency_context(**kwargs)
    return ScorerService(context=context)


def get_scorer_service() -> IScorerService:
    return create_scorer_service()


class _LazyScorerServiceProxy(IScorerService):
    """Lazy Singleton Proxy for ScorerService.

    Defers actual instantiation to first access to avoid import-time overhead and
    circular dependencies.
    """

    def __init__(self) -> None:
        self._instance: Optional[IScorerService] = None

    def _get_service(self) -> IScorerService:
        if self._instance is None:
            self._instance = get_scorer_service()
        return self._instance

    def score_account(
        self,
        command: ScoreAccountCommand,
    ) -> AccountScore:
        return self._get_service().score_account(command=command)

    def score_batch(
        self,
        command: BatchScoreCommand,
    ) -> List[AccountScore]:
        return self._get_service().score_batch(command=command)

    def save_score(self, score: AccountScore) -> dict:
        return self._get_service().save_score(score)

    def get_latest_score(
        self, account_key: str, version: Optional[str] = None
    ) -> Optional[LatestScoreResponse]:
        return self._get_service().get_latest_score(account_key, version=version)

    def get_score_history(
        self, account_key: str, version: Optional[str] = None
    ) -> List[ScoreHistoryItem]:
        return self._get_service().get_score_history(account_key, version=version)

    def format_account_context(self, account: Account) -> str:
        return self._get_service().format_account_context(account)

    def get_prompt(
        self,
        query: GetPromptQuery,
    ) -> str:
        return self._get_service().get_prompt(query=query)

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return self._get_service().calculate_cost(input_tokens, output_tokens)

    def get_summary(self) -> LLMStats:
        return self._get_service().get_summary()

    def set_accounts_service(self, accounts_service: IAccountsService) -> None:
        self._get_service().set_accounts_service(accounts_service)


default_scorer_service: IScorerService = _LazyScorerServiceProxy()


def get_user_scorer(
    current_user: Optional[Any] = Depends(get_current_user_optional),
) -> IScorerService:
    api_key: Optional[str] = None
    if current_user:
        from src.services.auth.dependencies import default_auth_service

        user_id = getattr(current_user, "id", None) or (
            current_user.get("id") if isinstance(current_user, dict) else None
        )
        if user_id:
            api_key = default_auth_service.get_user_api_key(user_id)

    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise InvalidInputError(
            message=(
                "Gemini API key not configured. Please open Profile settings and "
                "add your Google Gemini API key to run AI scoring."
            ),
            code="MISSING_GEMINI_API_KEY",
        )
    return create_scorer_service(api_key=api_key)
