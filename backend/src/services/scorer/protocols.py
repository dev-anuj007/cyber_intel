from typing import Any, List, Optional, Protocol, runtime_checkable

from src.services.accounts.types import Account
from src.services.scorer.types import (
    AccountScore,
    BatchScoreCommand,
    GetPromptQuery,
    LatestScoreResponse,
    LLMStats,
    ScoreAccountCommand,
    ScoreHistoryItem,
)


@runtime_checkable
class IScoreReader(Protocol):
    def get_latest_score(
        self, conn: Any, account_key: str, version: Optional[str] = None
    ) -> Optional[dict]: ...

    def get_score_history(
        self, conn: Any, account_key: str, version: Optional[str] = None
    ) -> List[dict]: ...

    def get_llm_stats(self, conn: Any) -> dict: ...


@runtime_checkable
class IScoreWriter(Protocol):
    def save_score(self, conn: Any, score: AccountScore) -> dict: ...


@runtime_checkable
class IScorerService(Protocol):
    def score_account(
        self,
        command: ScoreAccountCommand,
    ) -> AccountScore: ...

    def score_batch(
        self,
        command: BatchScoreCommand,
    ) -> List[AccountScore]: ...

    def save_score(self, score: AccountScore) -> dict: ...

    def get_latest_score(
        self, account_key: str, version: Optional[str] = None
    ) -> Optional[LatestScoreResponse]: ...

    def get_score_history(
        self, account_key: str, version: Optional[str] = None
    ) -> List[ScoreHistoryItem]: ...

    def format_account_context(self, account: Account) -> str: ...

    def get_prompt(
        self,
        query: GetPromptQuery,
    ) -> str: ...

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float: ...

    def get_summary(self) -> LLMStats: ...

    def set_accounts_service(self, accounts_service: Any) -> None: ...
