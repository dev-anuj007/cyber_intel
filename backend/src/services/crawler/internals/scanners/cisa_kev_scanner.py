import asyncio
import socket
from typing import List, Optional, Set

import httpx

from src.services.accounts.types import Asset, SecuritySignal
from src.services.aggregator.internals.domain_utils import normalize_domain
from src.services.crawler.internals.scanners.constants import CURATED_CISA_KEV_RULES
from src.services.crawler.internals.scanners.types import (
    ScannerEngineOptions,
    ScanResult,
    VulnerabilityFinding,
)
from src.services.logger.logger_service import BaseLogger, get_logger


class CisaKevScanner:
    scanner_type: str = "cisa_kev"
    display_name: str = "CISA KEV & Exploited CVE Threat Feed"
    description: str = (
        "Correlates perimeter banners, technologies, and products against the "
        "official CISA Known Exploited Vulnerabilities catalog."
    )

    def __init__(
        self,
        timeout: float = 2.0,
        logger: Optional[BaseLogger] = None,
    ):
        self.timeout = timeout
        self._logger = logger or get_logger("crawler.scanners.cisa_kev")

    async def scan_async(
        self,
        domain: str,
        options: Optional[ScannerEngineOptions] = None,
    ) -> ScanResult:
        opts = options or ScannerEngineOptions()
        clean_domain = normalize_domain(domain)
        timeout = opts.timeout if opts.timeout is not None else self.timeout

        try:
            ip = await asyncio.to_thread(socket.gethostbyname, clean_domain)
        except Exception:
            ip = None

        assets: List[Asset] = [Asset(ip=ip, port=443, hostname=clean_domain)] if ip else []
        signals: List[SecuritySignal] = []
        products: Set[str] = set()
        cloud_providers: Set[str] = set()
        matched_cves: List[str] = []
        vulnerabilities: List[VulnerabilityFinding] = []

        all_text_fingerprints: List[str] = []
        user_agent = {"User-Agent": "CISA-KEV-Threat-Audit/1.0"}
        async with httpx.AsyncClient(verify=False, timeout=timeout, follow_redirects=True) as client:
            try:
                resp = await client.get(
                    f"https://{clean_domain}",
                    headers=user_agent,
                )
                headers_str = " ".join([f"{k}:{v}" for k, v in resp.headers.items()]).lower()
                all_text_fingerprints.append(headers_str)
                all_text_fingerprints.append(resp.text[:2000].lower())
                srv = resp.headers.get("server", "")
                if srv:
                    products.add(srv)
            except Exception:
                try:
                    resp = await client.get(
                        f"http://{clean_domain}",
                        headers=user_agent,
                    )
                    headers_str = " ".join([f"{k}:{v}" for k, v in resp.headers.items()]).lower()
                    all_text_fingerprints.append(headers_str)
                    all_text_fingerprints.append(resp.text[:2000].lower())
                    srv = resp.headers.get("server", "")
                    if srv:
                        products.add(srv)
                except Exception:
                    pass

        joined_fingerprint = " ".join(all_text_fingerprints)

        for rule in CURATED_CISA_KEV_RULES:
            if any(kw in joined_fingerprint for kw in rule["keywords"]):
                matched_cves.append(rule["cve"])
                evidence_text = (
                    f"Perimeter product matches CISA KEV signature for "
                    f"{rule['vendor']} {rule['product']}. Known exploited in the wild."
                )
                signals.append(
                    SecuritySignal(
                        name=f"CISA KEV Alert: {rule['name']} ({rule['cve']})",
                        severity=rule["severity"],
                        category="cisa-kev",
                        evidence=evidence_text,
                    )
                )
                vulnerabilities.append(
                    VulnerabilityFinding(
                        id=rule["cve"],
                        name=rule["name"],
                        vendor=rule["vendor"],
                        product=rule["product"],
                        severity=rule["severity"].value.capitalize(),
                        source="CISA Known Exploited Vulnerabilities Catalog",
                    )
                )

        return ScanResult(
            domain=clean_domain,
            scanner_type=self.scanner_type,
            assets=assets,
            signals=signals,
            ips=[ip] if ip else [],
            hostnames=[clean_domain] if ip else [],
            ports=[443] if ip else [],
            products=list(products),
            cloud_providers=list(cloud_providers),
            vulnerabilities=vulnerabilities,
            cves=matched_cves,
            metadata={
                "engine": "cisa_kev_threat_intel",
                "matched_cve_count": len(matched_cves),
                "cisa_rules_evaluated": len(CURATED_CISA_KEV_RULES),
            },
        )

    def scan(
        self,
        domain: str,
        options: Optional[ScannerEngineOptions] = None,
    ) -> ScanResult:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, self.scan_async(domain, options)).result()
        return asyncio.run(self.scan_async(domain, options))
