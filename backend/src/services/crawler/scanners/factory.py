import concurrent.futures
from typing import Any, Dict, List, Optional, Set

from src.services.accounts.types import Asset, SecuritySignal
from src.services.crawler.scanners.base import ScanResult
from src.services.crawler.scanners.cisa_kev_scanner import CisaKevScanner
from src.services.crawler.scanners.owasp_zap_scanner import OwaspZapScanner
from src.services.crawler.scanners.projectdiscovery_scanner import ProjectDiscoveryScanner
from src.services.crawler.scanners.standard_scanner import StandardCrawlerScanner
from src.services.logger import get_logger

logger = get_logger("crawler.scanners.factory")


class ScannerFactory:
    _registry: Dict[str, Any] = {
        "standard": StandardCrawlerScanner,
        "owasp_zap": OwaspZapScanner,
        "projectdiscovery": ProjectDiscoveryScanner,
        "cisa_kev": CisaKevScanner,
    }

    @classmethod
    def register_scanner(cls, scanner_type: str, scanner_cls: Any) -> None:
        cls._registry[scanner_type.lower()] = scanner_cls

    @classmethod
    def get_scanner(cls, scanner_type: str = "standard", **kwargs) -> Any:
        st = scanner_type.lower()
        scanner_cls = cls._registry.get(st)
        if not scanner_cls:
            raise ValueError(f"Unknown scanner type: '{scanner_type}'. Available: {list(cls._registry.keys())}")
        return scanner_cls(**kwargs)

    @classmethod
    def list_available_scanners(cls) -> List[Dict[str, Any]]:
        result = [
            {
                "id": "all",
                "name": "Comprehensive Security Suite (All Engines)",
                "description": "Orchestrates Standard Network Crawler, OWASP ZAP DAST, ProjectDiscovery (Subfinder/HTTPX/Nuclei), and CISA KEV feeds simultaneously.",
                "badge": "Recommended · Full Depth",
                "icon": "🚀",
            }
        ]
        for key, s_cls in cls._registry.items():
            instance = s_cls()
            icon = (
                "🌐"
                if key == "standard"
                else "🛡️"
                if key == "owasp_zap"
                else "⚡"
                if key == "projectdiscovery"
                else "🚨"
            )
            badge = "Active"
            result.append(
                {
                    "id": key,
                    "name": instance.display_name,
                    "description": instance.description,
                    "badge": badge,
                    "icon": icon,
                }
            )
        return result

    @classmethod
    def run_scan(cls, domain: str, scanner_type: str = "all", options: Optional[Dict[str, Any]] = None) -> ScanResult:
        options = options or {}
        st = (scanner_type or "all").lower()

        if st != "all" and st in cls._registry:
            scanner = cls.get_scanner(st)
            return scanner.scan(domain, options)

        # Composite Run ("all"): Execute all registered scanners in parallel
        scanners_to_run = [cls._registry[k]() for k in ("standard", "owasp_zap", "projectdiscovery", "cisa_kev")]

        results: List[ScanResult] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(scanners_to_run)) as executor:
            future_to_s = {executor.submit(s.scan, domain, options): s for s in scanners_to_run}
            for future in concurrent.futures.as_completed(future_to_s):
                try:
                    res = future.result()
                    results.append(res)
                except Exception as e:
                    logger.warning(f"Error in scanner execution: {e}")

        # Merge Results
        merged_assets: List[Asset] = []
        seen_assets: Set[tuple] = set()
        merged_signals: List[SecuritySignal] = []
        seen_signals: Set[tuple] = set()
        merged_ips: Set[str] = set()
        merged_hostnames: Set[str] = set()
        merged_ports: Set[int] = set()
        merged_products: Set[str] = set()
        merged_cloud_providers: Set[str] = set()
        merged_vulnerabilities: List[Dict[str, Any]] = []
        merged_cves: Set[str] = set()

        for r in results:
            for a in r.assets:
                tup = (a.ip, a.port, a.hostname)
                if tup not in seen_assets:
                    seen_assets.add(tup)
                    merged_assets.append(a)

            for s in r.signals:
                s_sev = s.severity.value if hasattr(s.severity, "value") else str(s.severity)
                tup = (s.name, s_sev, getattr(s, "category", ""), s.evidence)
                if tup not in seen_signals:
                    seen_signals.add(tup)
                    merged_signals.append(s)

            merged_ips.update(r.ips)
            merged_hostnames.update(r.hostnames)
            merged_ports.update(r.ports)
            merged_products.update(r.products)
            merged_cloud_providers.update(r.cloud_providers)
            merged_vulnerabilities.extend(r.vulnerabilities)
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
