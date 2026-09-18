from typing import Protocol, List, Dict, Any, Optional, Tuple
from pydantic import BaseModel


class CrawlerRunRequest(BaseModel):
    domains: List[str]
    scan_depth: str = "standard"
    scanner_type: str = "all"
    enable_subdomains: bool = True
    custom_ports: Optional[List[int]] = None
    save_to_database: bool = True


class CrawlerJobSubmitRequest(BaseModel):
    domains: List[str]
    pipeline_name: Optional[str] = None
    scan_depth: str = "standard"
    scanner_type: str = "all"
    enable_subdomains: bool = True
    custom_ports: Optional[List[int]] = None
    save_to_database: bool = True


class CrawlerJobSubmitResponse(BaseModel):
    success: bool
    job_id: str
    status: str
    domains_count: int
    message: str
    trace_id: Optional[str] = None


class CrawlerJobSummary(BaseModel):
    job_id: str
    status: str
    domains_count: int
    completed_count: int
    assets_discovered_count: int
    signals_detected_count: int
    scan_depth: str
    scanner_type: str = "all"
    retry_count: int
    max_retries: int
    domains_preview: List[str]
    error_message: Optional[str] = None
    trace_id: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None


class CrawlerJobDetail(BaseModel):
    job_id: str
    status: str
    domains_count: int
    completed_count: int
    assets_discovered_count: int
    signals_detected_count: int
    scan_depth: str
    scanner_type: str = "all"
    enable_subdomains: bool
    save_to_database: bool
    custom_ports: Optional[List[int]] = None
    retry_count: int
    max_retries: int
    domains: List[str]
    results: List[Dict[str, Any]]
    error_message: Optional[str] = None
    trace_id: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None


class CrawlerJobListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    items: List[CrawlerJobSummary]


class ICrawlerReader(Protocol):
    def get_cached_scan(self, domain: str) -> Optional[dict]:
        ...


class ICrawlerWriter(Protocol):
    def cache_scan(self, domain: str, scan_data: dict) -> None:
        ...


class ICrawlerJobsRepository(Protocol):
    def create_job(self, conn, **kwargs) -> str:
        ...

    def get_job(self, conn, job_id: str) -> Optional[Dict[str, Any]]:
        ...

    def list_jobs(self, conn, skip: int = 0, limit: int = 20, status: Optional[str] = None) -> Tuple[List[Dict[str, Any]], int]:
        ...

    def update_job_status(self, conn, job_id: str, status: str, error_message: Optional[str] = None) -> None:
        ...

    def update_job_progress(self, conn, job_id: str, completed_count: int, assets_count: int, signals_count: int, results: List[Dict[str, Any]]) -> None:
        ...

    def complete_job(self, conn, job_id: str, results: List[Dict[str, Any]], assets_count: int, signals_count: int) -> None:
        ...

    def fail_job(self, conn, job_id: str, error_message: str) -> None:
        ...


class ICrawlerService(Protocol):
    def resolve_ip(self, host: str) -> Optional[str]:
        ...

    def probe_http_banner(self, host: str, port: int) -> Dict[str, Any]:
        ...

    def check_port_open(self, ip: str, port: int) -> bool:
        ...

    def crawl_domain(
        self,
        domain: str,
        scan_depth: str = "standard",
        enable_subdomains: bool = True,
        custom_ports: Optional[List[int]] = None,
        save_to_database: bool = False,
    ) -> Dict[str, Any]:
        ...
