from typing import Any, Dict, List, Optional, TypedDict

from pydantic import BaseModel

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
    domain: str
    scanner_type: str
    assets: List[Asset] = []
    signals: List[SecuritySignal] = []
    ips: List[str] = []
    hostnames: List[str] = []
    ports: List[int] = []
    products: List[str] = []
    cloud_providers: List[str] = []
    vulnerabilities: List[VulnerabilityFinding] = []
    cves: List[str] = []
    metadata: Dict[str, Any] = {}
