from typing import Any, Dict, List, Optional, Protocol

from pydantic import BaseModel

from src.services.accounts.types import Asset, SecuritySignal


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
    vulnerabilities: List[Dict[str, Any]] = []
    cves: List[str] = []
    metadata: Dict[str, Any] = {}


class IScanner(Protocol):
    scanner_type: str
    display_name: str
    description: str

    def scan(self, domain: str, options: Optional[Dict[str, Any]] = None) -> ScanResult: ...
