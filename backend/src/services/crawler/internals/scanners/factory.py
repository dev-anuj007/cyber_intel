import asyncio
from typing import Callable, Dict, List, Optional, Set

from src.services.accounts.types import Asset, SecuritySignal
from src.services.crawler.internals.scanners.cisa_kev_scanner import CisaKevScanner
from src.services.crawler.internals.scanners.owasp_zap_scanner import OwaspZapScanner
from src.services.crawler.internals.scanners.projectdiscovery_scanner import (
    ProjectDiscoveryScanner,
)
from src.services.crawler.internals.scanners.protocols import IScanner
from src.services.crawler.internals.scanners.standard_scanner import (
    StandardCrawlerScanner,
)
from src.services.crawler.internals.scanners.types import (
    ScannerCatalogItem,
    ScannerEngineOptions,
    ScanResult,
    VulnerabilityFinding,
)
from src.services.logger.logger_service import BaseLogger, get_logger


class ScannerFactory:
    _registry: Dict[str, Callable[..., IScanner]] = {
        "standard": StandardCrawlerScanner,
        "owasp_zap": OwaspZapScanner,
        "projectdiscovery": ProjectDiscoveryScanner,
        "cisa_kev": CisaKevScanner,
    }

    @classmethod
    def register_scanner(
        cls, scanner_type: str, scanner_cls: Callable[..., IScanner]
    ) -> None:
        cls._registry[scanner_type.lower()] = scanner_cls

    @classmethod
    def get_scanner(
        cls,
        scanner_type: str = "standard",
        logger: Optional[BaseLogger] = None,
        **kwargs,
    ) -> IScanner:
        st = scanner_type.lower()
        scanner_cls = cls._registry.get(st)
        if not scanner_cls:
            available = list(cls._registry.keys())
            raise ValueError(
                f"Unknown scanner type: '{scanner_type}'. Available: {available}"
            )
        return scanner_cls(logger=logger, **kwargs)

    @classmethod
    def list_available_scanners(cls) -> List[ScannerCatalogItem]:
        result = [
            ScannerCatalogItem(
                id="all",
                name="Comprehensive Security Suite (All Engines)",
                description=(
                    "Orchestrates Standard Network Crawler, OWASP ZAP DAST, "
                    "ProjectDiscovery (Subfinder/HTTPX/Nuclei), and CISA KEV "
                    "feeds simultaneously."
                ),
                badge="Recommended - Full Depth",
                icon="all",
            )
        ]
        for key, s_cls in cls._registry.items():
            instance = s_cls()
            icon = (
                "network"
                if key == "standard"
                else "dast"
                if key == "owasp_zap"
                else "recon"
                if key == "projectdiscovery"
                else "threat_intel"
            )
            badge = "Active"
            result.append(
                ScannerCatalogItem(
                    id=key,
                    name=instance.display_name,
                    description=instance.description,
                    badge=badge,
                    icon=icon,
                )
            )
        return result

    @classmethod
    async def run_scan_async(
        cls,
        domain: str,
        scanner_type: str = "all",
        options: Optional[ScannerEngineOptions] = None,
        logger: Optional[BaseLogger] = None,
    ) -> ScanResult:
        opts = options or ScannerEngineOptions()
        st = (scanner_type or "all").lower()
        active_logger = logger or get_logger("crawler.scanners.factory")

        if st != "all" and st in cls._registry:
            scanner = cls.get_scanner(st, logger=active_logger)
            if hasattr(scanner, "scan_async"):
                return await scanner.scan_async(domain, opts)
            return await asyncio.to_thread(scanner.scan, domain, opts)

        scanners_to_run = [
            s_cls(logger=active_logger) for s_cls in cls._registry.values()
        ]

        async def run_single_scanner(s: IScanner) -> Optional[ScanResult]:
            try:
                if hasattr(s, "scan_async"):
                    return await s.scan_async(domain, opts)
                return await asyncio.to_thread(s.scan, domain, opts)
            except Exception as e:
                active_logger.warning(
                    f"Error executing scanner {s.scanner_type}: {e}"
                )
                return None

        scan_outputs = await asyncio.gather(
            *[run_single_scanner(s) for s in scanners_to_run],
            return_exceptions=True,
        )

        results: List[ScanResult] = [
            res
            for res in scan_outputs
            if isinstance(res, ScanResult) and res is not None
        ]

        merged_assets: List[Asset] = []
        seen_assets: Set[tuple] = set()
        merged_signals: List[SecuritySignal] = []
        seen_signals: Set[tuple] = set()
        merged_ips: Set[str] = set()
        merged_hostnames: Set[str] = set()
        merged_ports: Set[int] = set()
        merged_products: Set[str] = set()
        merged_cloud_providers: Set[str] = set()
        merged_vulnerabilities: List[VulnerabilityFinding] = []
        seen_vulnerabilities: Set[str] = set()
        merged_cves: Set[str] = set()

        for r in results:
            for a in r.assets:
                tup = (a.ip, a.port, a.hostname)
                if tup not in seen_assets:
                    seen_assets.add(tup)
                    merged_assets.append(a)

            for s in r.signals:
                s_sev = (
                    s.severity.value
                    if hasattr(s.severity, "value")
                    else str(s.severity)
                )
                tup = (s.name, s_sev, getattr(s, "category", ""), s.evidence)
                if tup not in seen_signals:
                    seen_signals.add(tup)
                    merged_signals.append(s)

            for v in r.vulnerabilities:
                if v.id not in seen_vulnerabilities:
                    seen_vulnerabilities.add(v.id)
                    merged_vulnerabilities.append(v)

            merged_ips.update(r.ips)
            merged_hostnames.update(r.hostnames)
            merged_ports.update(r.ports)
            merged_products.update(r.products)
            merged_cloud_providers.update(r.cloud_providers)
            merged_cves.update(r.cves)

        return ScanResult(
            domain=domain,
            scanner_type="all",
            assets=merged_assets,
            signals=merged_signals,
            ips=list(merged_ips),
            hostnames=list(merged_hostnames),
            ports=sorted(list(merged_ports)),
            products=list(merged_products),
            cloud_providers=list(merged_cloud_providers),
            vulnerabilities=merged_vulnerabilities,
            cves=list(merged_cves),
            metadata={
                "engine": "composite_full_security_suite",
                "engines_executed": [s.scanner_type for s in scanners_to_run],
                "total_signals_detected": len(merged_signals),
                "total_assets_discovered": len(merged_assets),
            },
        )

    @classmethod
    def run_scan(
        cls,
        domain: str,
        scanner_type: str = "all",
        options: Optional[ScannerEngineOptions] = None,
        logger: Optional[BaseLogger] = None,
    ) -> ScanResult:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(
                    asyncio.run,
                    cls.run_scan_async(domain, scanner_type, options, logger),
                ).result()
        return asyncio.run(cls.run_scan_async(domain, scanner_type, options, logger))
