from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.services.accounts.types import Account, SecuritySignal
from src.services.crawler.internals.scanners.types import (
    ScannerCatalogItem,
    VulnerabilityFinding,
)


class CrawlerScanRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    domain: str
    scan_depth: str = "standard"
    scanner_type: str = "standard"
    enable_subdomains: bool = True
    custom_ports: Optional[List[int]] = None
    save_to_database: bool = False


class CrawlerRunRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    domains: List[str]
    scan_depth: str = "standard"
    scanner_type: str = "all"
    enable_subdomains: bool = True
    custom_ports: Optional[List[int]] = None
    save_to_database: bool = True


class CrawlerJobSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    domains: List[str]
    pipeline_name: Optional[str] = None
    scan_depth: str = "standard"
    scanner_type: str = "all"
    enable_subdomains: bool = True
    custom_ports: Optional[List[int]] = None
    save_to_database: bool = True


class CrawlerJobSubmitResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    success: bool
    job_id: str
    status: str
    domains_count: int
    message: str
    trace_id: Optional[str] = None


class CrawlerScanResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    domain: str
    account_key: str
    version: str
    scanner_type: str
    scan_depth: str
    elapsed_ms: int
    discovered_hosts: List[str] = Field(default_factory=list)
    assets_count: int = 0
    ips_count: int = 0
    ports_discovered: List[int] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)
    cloud_providers: List[str] = Field(default_factory=list)
    signals_detected_count: int = 0
    vulnerabilities_count: int = 0
    vulnerabilities: List[VulnerabilityFinding] = Field(default_factory=list)
    cves: List[str] = Field(default_factory=list)
    signals: List[SecuritySignal] = Field(default_factory=list)
    account: Optional[Account] = None
    error: Optional[str] = None


class CrawlerScannersResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scanners: List[ScannerCatalogItem]


class CrawlerSingleScanResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    success: bool
    domain: str
    scanner_type: str
    result: CrawlerScanResult


class CrawlerRunResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    success: bool
    total_crawled: int
    results: List[CrawlerScanResult] = Field(default_factory=list)
    timestamp: str


class CrawlerBatchMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    assets_discovered_count: int = 0
    signals_detected_count: int = 0
    domains_count: int = 0
    scan_depth: str = "standard"
    scanner_type: str = "all"


class CrawlerBatchResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    results: List[CrawlerScanResult] = Field(default_factory=list)
    metadata: CrawlerBatchMetadata
