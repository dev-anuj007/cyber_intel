from typing import Any, Dict, List, Optional, Protocol, Union, runtime_checkable

from src.services.accounts.types import Account
from src.services.scorer.types import (
    AccountScore,
    BatchScoreCommand,
    LLMTrace,
    ScoreAccountCommand,
)


@runtime_checkable
class IScoreReader(Protocol):
    def get_latest_score(self, conn: Any, account_key: str, version: Optional[str] = None) -> Optional[dict]: ...

    def get_score_history(self, conn: Any, account_key: str, version: Optional[str] = None) -> List[dict]: ...


@runtime_checkable
class IScoreWriter(Protocol):
    def save_score(self, conn: Any, score: Union[AccountScore, dict]) -> dict: ...


@runtime_checkable
class IScorerService(Protocol):
    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float: ...

    def format_account_context(self, account: Union[Account, Dict[str, Any], Any]) -> str: ...

    def get_prompt(
        self,
        account: Union[Account, Dict[str, Any], Any],
        prompt_version: Optional[str] = None,
        custom_prompt_template: Optional[str] = None,
    ) -> str: ...

    def score_account(
        self,
        account: Union[Account, Dict[str, Any], ScoreAccountCommand, Any],
        prompt_version: Optional[str] = None,
        custom_prompt_template: Optional[str] = None,
        save_to_db: bool = True,
    ) -> AccountScore: ...

    def score_batch(
        self,
        account_keys: Union[List[str], BatchScoreCommand],
        limit: int = 10,
    ) -> List[AccountScore]: ...

    def get_latest_score(self, account_key: str) -> Optional[dict]: ...

    def get_score_history(self, account_key: str) -> List[dict]: ...

    def get_latest_score_for_account(self, account_key: str, version: Optional[str] = None) -> Optional[dict]: ...

    def get_score_history_for_account(self, account_key: str, version: Optional[str] = None) -> List[dict]: ...

    def log_trace(self, trace: LLMTrace) -> None: ...

    def get_traces(self) -> List[LLMTrace]: ...

    def get_summary(self) -> Dict[str, Any]: ...



