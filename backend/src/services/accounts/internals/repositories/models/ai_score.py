from typing import Optional

from sqlmodel import Field, SQLModel


class AIScoreTable(SQLModel, table=True):
    __tablename__: str = "ai_scores"  # type: ignore
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    account_key: str = Field(index=True)
    version: int = Field(default=1)
    score: int
    priority_tier: str
    key_risks: str
    suggested_outreach: str
    score_rationale: Optional[str] = ""
    model_version: str
    model_name: Optional[str] = "gemini-3.1-flash-lite"
    tokens_used: Optional[str] = None
    latency_ms: Optional[int] = 0
    cost_usd: Optional[float] = 0.0
    scored_at: Optional[str] = None
    is_latest: Optional[int] = 1
