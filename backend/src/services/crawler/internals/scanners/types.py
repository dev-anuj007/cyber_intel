from typing import Any, Dict, List, Optional, TypedDict

from pydantic import BaseModel, ConfigDict, Field

from src.services.accounts.types import Asset, SecuritySignal, SignalSeverity


class ProbeResult(TypedDict):
    host: str
    ip: Optional[str]
    port: int
    banner: Dict[str, Any]


class KevRule(TypedDict):
    cve: str
    vendor: str
    product: str
    name: str
    keywords: List[str]
    severity: SignalSeverity
    due_date: str


class VulnerabilityFinding(BaseModel):
    id: str
    name: str
    severity: str
    cwe: Optional[str] = None
    vendor: Optional[str] = None
    product: Optional[str] = None
    url: Optional[str] = None
    port: Optional[int] = None
    source: Optional[str] = None


class ScannerCatalogItem(BaseModel):
    id: str
    name: str
    description: str
    badge: str
    icon: str


class ScannerEngineOptions(BaseModel):
    scan_depth: str = "standard"
    enable_subdomains: bool = True
    custom_ports: Optional[List[int]] = None
    timeout: float = 0.8


class ScanResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    domain: str
    scanner_type: str
    assets: List[Asset] = Field(default_factory=list)
    signals: List[SecuritySignal] = Field(default_factory=list)
    ips: List[str] = Field(default_factory=list)
    hostnames: List[str] = Field(default_factory=list)
    ports: List[int] = Field(default_factory=list)
    products: List[str] = Field(default_factory=list)
    cloud_providers: List[str] = Field(default_factory=list)
    vulnerabilities: List[VulnerabilityFinding] = Field(default_factory=list)
    cves: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
