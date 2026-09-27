from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class BackgroundJobTable(SQLModel, table=True):
    __tablename__: str = "background_jobs"  # type: ignore
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: str = Field(unique=True, index=True)
    job_type: str = Field(index=True)
    title: str
    user_id: Optional[int] = None
    status: str = Field(default="queued", index=True)
    progress_current: int = Field(default=0)
    progress_total: int = Field(default=1)
    retry_count: int = Field(default=0)
    max_retries: int = Field(default=3)
    payload_json: Optional[str] = "{}"
    results_json: Optional[str] = "null"
    metadata_json: Optional[str] = "{}"
    error_message: Optional[str] = None
    trace_id: Optional[str] = None
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
