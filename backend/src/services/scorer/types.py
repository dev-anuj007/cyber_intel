from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from src.services.accounts.types import Account


class PriorityTier(str, Enum):
    TIER_1_CRITICAL = "tier_1_critical"
    TIER_2_HIGH = "tier_2_high"
    TIER_3_MEDIUM = "tier_3_medium"
    TIER_4_LOW = "tier_4_low"


class AccountScore(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True, extra="ignore")

    account_key: str
    account: Union[Account, Dict[str, Any], Any] = {}
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
    key_risks: Optional[List[str]] = None
    suggested_outreach: Optional[str] = None
    timestamp: Optional[datetime] = None
    tokens_used: Optional[Dict[str, int]] = None
    latency_ms: Optional[int] = None


class LLMTrace(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    trace_id: Optional[str] = None
    id: Optional[str] = None
    account_key: str
    model: str
    prompt_version: str
    input_tokens: Optional[int] = 0
    output_tokens: Optional[int] = 0
    request_tokens: Optional[int] = 0
    response_tokens: Optional[int] = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None
    score: Optional[int] = None
    priority_tier: Optional[str] = None
    key_risks: Optional[List[str]] = None
    suggested_outreach: Optional[str] = None


class ScoreAccountCommand(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    account: Union[Account, Dict[str, Any], Any]
    prompt_version: Optional[str] = None
    custom_prompt_template: Optional[str] = None
    save_to_db: bool = True


class BatchScoreCommand(BaseModel):
    account_keys: List[str]
    limit: int = 10
    prompt_version: Optional[str] = None


class ScoringRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    account: Union[Account, Dict[str, Any], Any]
    use_cot: bool = True
    account_key: Optional[str] = None


class ScoringResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    success: bool
    score: Optional[AccountScore] = None
    error: Optional[str] = None


class LLMStats(BaseModel):
    total_calls: int
    total_tokens: int
    total_cost_usd: float
    avg_latency_ms: float
    trace_file: Optional[str] = None



