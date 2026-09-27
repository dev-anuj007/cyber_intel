from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.services.accounts.types import Account, SecuritySignal


class PriorityTier(str, Enum):
    TIER_1_CRITICAL = "tier_1_critical"
    TIER_2_HIGH = "tier_2_high"
    TIER_3_MEDIUM = "tier_3_medium"
    TIER_4_LOW = "tier_4_low"


class AccountScore(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True, populate_by_name=True, extra="ignore"
    )

    account_key: str
    account: Optional[Account] = None
    score: int = 0
    score_rationale: Optional[str] = ""
    reasoning: Optional[str] = ""
    priority_tier: PriorityTier = PriorityTier.TIER_3_MEDIUM
    model: str = "gemini-2.5-flash"
    prompt_version: str = "v1.0"
    scoring_time_ms: int = 0
    cost_usd: float = 0.0
    input_tokens: Optional[int] = 0
    output_tokens: Optional[int] = 0
    total_tokens: Optional[int] = 0
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    outreach_strategy: Optional[str] = None
    first_party_intel: Optional[Dict[str, Any]] = None
    security_posture_score: Optional[int] = None
    business_impact_score: Optional[int] = None
    compliance_risk_score: Optional[int] = None

    # Compat fields for legacy repository records and tests
    version: Optional[int] = None
    model_version: Optional[str] = None
    model_name: Optional[str] = None
    key_risks: Optional[List[str]] = None
    suggested_outreach: Optional[str] = None
    timestamp: Optional[datetime] = None
    tokens_used: Optional[Dict[str, int]] = None
    latency_ms: Optional[int] = None


class ScoreAccountCommand(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    account: Account
    prompt_version: Optional[str] = None
    custom_prompt_template: Optional[str] = None
    save_to_db: bool = True


class BatchScoreCommand(BaseModel):
    model_config = ConfigDict(extra="ignore")

    account_keys: List[str]
    limit: int = 10
    prompt_version: Optional[str] = None


class GetPromptQuery(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    account: Account
    prompt_version: Optional[str] = None
    custom_prompt_template: Optional[str] = None


class CategorizedSignals(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    critical: List[SecuritySignal] = Field(default_factory=list)
    high: List[SecuritySignal] = Field(default_factory=list)
    medium: List[SecuritySignal] = Field(default_factory=list)
    low: List[SecuritySignal] = Field(default_factory=list)
    total_count: int = 0


class ScoringRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    account: Optional[Account] = None
    use_cot: bool = True
    account_key: Optional[str] = None
    prompt_version: Optional[str] = None


class ScoringResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    success: bool = True
    score: Optional[AccountScore] = None
    error: Optional[str] = None


class LLMStats(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_calls: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    avg_latency_ms: float = 0.0
    trace_file: Optional[str] = None


class LatestScoreResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    account_key: str
    score: int = 0
    priority_tier: str = "tier_4_low"
    version: int = 0
    key_risks: List[str] = Field(default_factory=list)
    suggested_outreach: str = "None"
    score_rationale: str = "No score recorded yet"
    model_version: Optional[str] = None
    model_name: Optional[str] = None
    tokens_used: Optional[Dict[str, int]] = None
    latency_ms: Optional[int] = None
    cost_usd: Optional[float] = None
    scored_at: Optional[str] = None


class ScoreHistoryItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: Optional[int] = None
    account_key: str
    version: int = 1
    score: int = 0
    priority_tier: str = "tier_4_low"
    key_risks: List[str] = Field(default_factory=list)
    suggested_outreach: str = "None"
    score_rationale: Optional[str] = None
    model_version: Optional[str] = None
    model_name: Optional[str] = None
    tokens_used: Optional[Dict[str, int]] = None
    latency_ms: Optional[int] = None
    cost_usd: Optional[float] = None
    scored_at: Optional[str] = None
    created_at: Optional[str] = None


class ScoreHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    account_key: str
    scores: List[ScoreHistoryItem] = Field(default_factory=list)
    total_versions: int = 0
