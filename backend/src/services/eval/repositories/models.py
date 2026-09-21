"""SQLModel models for Eval service."""

from typing import Optional

from sqlmodel import Field, SQLModel


class EvalRunTable(SQLModel, table=True):
    __tablename__: str = "eval_runs"  # type: ignore
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(unique=True, index=True)
    prompt_version: str
    total_samples: int = Field(default=0)
    tier_accuracy: float = Field(default=0.0)
    macro_f1: float = Field(default=0.0)
    weighted_f1: float = Field(default=0.0)
    critical_threat_recall: float = Field(default=0.0)
    score_tier_consistency: float = Field(default=0.0)
    score_mae: float = Field(default=0.0)
    score_rmse: float = Field(default=0.0)
    within_5_points: int = Field(default=0)
    within_5_points_pct: float = Field(default=0.0)
    tier_metrics_json: Optional[str] = "{}"
    predictions_json: Optional[str] = "[]"
    results_json: Optional[str] = "{}"
    created_at: Optional[str] = Field(default=None)
