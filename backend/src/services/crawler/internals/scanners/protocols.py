from typing import Optional, Protocol, runtime_checkable

from src.services.crawler.internals.scanners.types import (
    ScannerEngineOptions,
    ScanResult,
)


@runtime_checkable
class IScanner(Protocol):
    scanner_type: str
    display_name: str
    description: str

    def scan(
        self,
        domain: str,
        options: Optional[ScannerEngineOptions] = None,
    ) -> ScanResult: ...

    async def scan_async(
        self,
        domain: str,
        options: Optional[ScannerEngineOptions] = None,
    ) -> ScanResult: ...
