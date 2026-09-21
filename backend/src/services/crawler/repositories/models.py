"""SQLModel models for Crawler service."""

from typing import Optional

from sqlmodel import Field, SQLModel


class CrawlerJobTable(SQLModel, table=True):
    __tablename__: str = "crawler_jobs"  # type: ignore
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: str = Field(unique=True, index=True)
    user_id: Optional[int] = None
    status: str = Field(default="queued", index=True)
    scan_depth: str = Field(default="standard")
    enable_subdomains: int = Field(default=1)
    custom_ports: Optional[str] = None
    save_to_database: int = Field(default=1)
    domains_input: str = Field(default="[]")
    domains_count: int = Field(default=0)
    completed_count: int = Field(default=0)
    assets_discovered_count: int = Field(default=0)
    signals_detected_count: int = Field(default=0)
    retry_count: int = Field(default=0)
    max_retries: int = Field(default=3)
    results_json: Optional[str] = "[]"
    error_message: Optional[str] = None
    trace_id: Optional[str] = None
    created_at: Optional[str] = Field(default=None)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
