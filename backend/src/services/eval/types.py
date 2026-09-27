from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.services.accounts.types import Account
from src.services.scorer.types import PriorityTier


class EvalExample(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    account_key: str
    account: Account
    expected_tier: PriorityTier
    expected_score: int
    reasoning: str = ""


class EvalPredictionItem(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    expected_tier: str
    predicted_tier: str
    expected_score: int
    predicted_score: int
    tier_match: bool
    score_error: int
    score_tier_consistent: bool
    key_risks: List[str] = Field(default_factory=list)
    suggested_outreach: str = ""


class EvalMetricDetails(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    prompt_version: str = "v1.0"
    total: int = 0
    correct_tier: int = 0
    correct_score: int = 0
    tier_accuracy: float = 0.0
    macro_f1: float = 0.0
    weighted_f1: float = 0.0
    critical_threat_recall: float = 0.0
    score_tier_consistency: float = 0.0
    score_mae: float = 0.0
    score_rmse: float = 0.0
    within_5_points: int = 0
    within_5_points_pct: float = 0.0
    tier_metrics: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    predictions: List[EvalPredictionItem] = Field(default_factory=list)


class EvalRunResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    success: bool = True
    prompt_version: str
    results: EvalMetricDetails
    saved_file: Optional[str] = None
    timestamp: str


class PromptComparisonMetrics(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    prompt_a: str
    prompt_b: str
    accuracy_a: float = 0.0
    accuracy_b: float = 0.0
    accuracy_diff: float = 0.0
    macro_f1_a: float = 0.0
    macro_f1_b: float = 0.0
    macro_f1_diff: float = 0.0
    score_mae_a: float = 0.0
    score_mae_b: float = 0.0
    score_mae_diff: float = 0.0
    critical_recall_a: float = 0.0
    critical_recall_b: float = 0.0
    critical_recall_diff: float = 0.0
    tier_consistency_a: float = 0.0
    tier_consistency_b: float = 0.0
    tier_consistency_diff: float = 0.0
    tier_distribution_comparison: Dict[str, Any] = Field(default_factory=dict)


class EvalCompareResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    success: bool = True
    comparison: PromptComparisonMetrics
    results_a: EvalMetricDetails
    results_b: EvalMetricDetails
    timestamp: str


class EvalHistoryItem(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    run_id: str
    prompt_version: str
    total_samples: int = 0
    tier_accuracy: float = 0.0
    macro_f1: float = 0.0
    critical_threat_recall: float = 0.0
    created_at: Optional[str] = None
    filename: Optional[str] = None


class RunEvalCommand(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    prompt_version: str = "v2.0"
    custom_prompt_template: Optional[str] = None
    dry_run: bool = True
    api_key: Optional[str] = None
    eval_set_path: Optional[str] = None
    eval_set: Optional[List[Dict[str, Any]]] = None
    sample_limit: Optional[int] = None
    progress_callback: Optional[Any] = None


class ComparePromptsCommand(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    prompt_a: str = "v1.0"
    prompt_b: str = "v2.0"
    custom_prompt_a: Optional[str] = None
    custom_prompt_b: Optional[str] = None
    dry_run: bool = True
    file_a: Optional[str] = None
    file_b: Optional[str] = None
    api_key: Optional[str] = None
    eval_set_path: Optional[str] = None
    eval_set: Optional[List[Dict[str, Any]]] = None
    sample_limit: Optional[int] = None
    progress_callback: Optional[Any] = None


class EvalRunRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    prompt_version: str = "v2.0"
    custom_prompt_template: Optional[str] = None
    dry_run: bool = True
    eval_set_path: Optional[str] = None
    eval_set: Optional[List[Dict[str, Any]]] = None
    sample_limit: Optional[int] = None


class EvalCompareRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    prompt_a: str = "v1.0"
    prompt_b: str = "v2.0"
    custom_prompt_a: Optional[str] = None
    custom_prompt_b: Optional[str] = None
    dry_run: bool = True
    file_a: Optional[str] = None
    file_b: Optional[str] = None
    eval_set_path: Optional[str] = None
    eval_set: Optional[List[Dict[str, Any]]] = None
    sample_limit: Optional[int] = None
