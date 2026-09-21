from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Union

from pydantic import BaseModel, ConfigDict

from src.services.accounts.types import Account


class PriorityTier(str, Enum):
    TIER_1_CRITICAL = "tier_1_critical"
    TIER_2_HIGH = "tier_2_high"
    TIER_3_MEDIUM = "tier_3_medium"
    TIER_4_LOW = "tier_4_low"


class AccountScore(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    account_key: str
    account: Union[Account, Dict[str, Any], Any]
    score: int
    score_rationale: Optional[str] = ""
    priority_tier: PriorityTier
    key_risks: List[str] = []
    suggested_outreach: str = ""
    model_version: str
    model_name: Optional[str] = "gemini-3.1-flash-lite"
    timestamp: datetime
    tokens_used: dict = {}
    latency_ms: int = 0
    cost_usd: float = 0.0
    version: Optional[int] = None


class LLMTrace(BaseModel):
    id: str
    timestamp: datetime
    model: str
    prompt_version: str
    account_key: str
    request_tokens: int
    response_tokens: int
    total_tokens: int
    latency_ms: int
    cost_usd: float
    score: int
    priority_tier: str
    key_risks: List[str] = []
    suggested_outreach: str = ""


class ScoringRequest(BaseModel):
    account_key: Optional[str] = None
    account: Optional[Account] = None
    prompt_version: Optional[str] = None


class ScoringResponse(BaseModel):
    score: int
    priority_tier: PriorityTier
    key_risks: List[str]
    suggested_outreach: str
    score_rationale: str


class LLMStats(BaseModel):
    total_calls: int
    total_tokens: int
    total_cost_usd: float
    avg_latency_ms: float
    trace_file: Optional[str] = None


class IScoreReader(Protocol):
    """Score data reader contract."""

    def get_latest_score(
        self, conn: Any, account_key: str, version: Optional[str] = None
    ) -> Optional[dict]: ...

    def get_score_history(
        self, conn: Any, account_key: str, version: Optional[str] = None
    ) -> List[dict]: ...


class IScoreWriter(Protocol):
    """Score data writer contract."""

    def save_score(self, conn: Any, score: AccountScore) -> dict: ...


class IScorerService(Protocol):
    """Scorer business service contract."""

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float: ...

    def format_account_context(self, account: Account) -> str: ...

    def get_prompt(
        self,
        account: Account,
        prompt_version: Optional[str] = None,
        custom_prompt_template: Optional[str] = None,
    ) -> str: ...

    def score_account(
        self,
        account: Account,
        prompt_version: Optional[str] = None,
        custom_prompt_template: Optional[str] = None,
    ) -> AccountScore: ...

    def score_batch(self, account_keys: List[str], limit: int = 10) -> List[AccountScore]: ...

    def get_latest_score_for_account(self, account_key: str, version: Optional[str] = None) -> Optional[dict]: ...

    def get_score_history_for_account(self, account_key: str, version: Optional[str] = None) -> List[dict]: ...

    def log_trace(self, trace: LLMTrace) -> None: ...

    def get_traces(self) -> List[LLMTrace]: ...

    def get_summary(self) -> Dict[str, Any]: ...
