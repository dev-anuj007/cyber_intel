from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict

from src.services.crawler.internals.scanners.types import (
    ScannerCatalogItem,
    VulnerabilityFinding,
)


class CrawlerScanRequest(BaseModel):
    domain: str
    scan_depth: str = "standard"
    scanner_type: str = "standard"
    enable_subdomains: bool = True
    custom_ports: Optional[List[int]] = None
    save_to_database: bool = False


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


class CrawlerScanResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    domain: str
    account_key: str
    version: str
    scanner_type: str
    scan_depth: str
    elapsed_ms: int
    discovered_hosts: List[str] = []
    assets_count: int = 0
    ips_count: int = 0
    ports_discovered: List[int] = []
    technologies: List[str] = []
    cloud_providers: List[str] = []
    signals_detected_count: int = 0
    vulnerabilities_count: int = 0
    vulnerabilities: List[Union[VulnerabilityFinding, Dict[str, Any], str]] = []
    cves: List[str] = []
    signals: List[Dict[str, Any]] = []
    account: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class CrawlerScannersResponse(BaseModel):
    scanners: List[ScannerCatalogItem]


class CrawlerSingleScanResponse(BaseModel):
    success: bool
    domain: str
    scanner_type: str
    result: CrawlerScanResult


class CrawlerRunResponse(BaseModel):
    success: bool
    total_crawled: int
    results: List[Dict[str, Any]]
    timestamp: str


class CrawlerBatchMetadata(BaseModel):
    assets_discovered_count: int = 0
    signals_detected_count: int = 0
    domains_count: int = 0
    scan_depth: str = "standard"
    scanner_type: str = "all"


class CrawlerBatchResult(BaseModel):
    results: List[Dict[str, Any]]
    metadata: CrawlerBatchMetadata
