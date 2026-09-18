import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

from src.services.accounts.types import Account, Asset, SecuritySignal
from src.services.aggregator.aggregator_service import normalize_domain
from src.services.crawler.types import (
    ICrawlerService,
    ICrawlerReader,
    ICrawlerWriter,
)
from src.services.crawler.repositories.reader import CrawlerReader
from src.services.crawler.repositories.writer import CrawlerWriter
from src.services.crawler.scanners import ScannerFactory
from src.services.jobs.jobs_service import default_jobs_service
from src.services.logger import get_logger

logger = get_logger("services.crawler")


class CrawlerService(ICrawlerService):
    def __init__(
        self,
        db_path: Optional[Path] = None,
        timeout: float = 0.8,
        max_subdomains: int = 12,
        ports: Optional[List[int]] = None,
        reader: Optional[ICrawlerReader] = None,
        writer: Optional[ICrawlerWriter] = None,
        accounts_service: Optional[Any] = None,
    ):
        self.db_path = db_path
        self.timeout = timeout
        self.max_subdomains = max_subdomains
        self.ports = ports or [80, 443, 8080, 8443]
        self.reader = reader or CrawlerReader()
        self.writer = writer or CrawlerWriter()
        self._accounts_service = accounts_service

    def set_accounts_service(self, accounts_service: Any) -> None:
        self._accounts_service = accounts_service

    def _get_accounts_service(self):
        if not self._accounts_service:
            from src.services.accounts.accounts_service import default_accounts_service
            self._accounts_service = default_accounts_service
        return self._accounts_service

    def _calculate_next_account_version(self, domain: str) -> tuple[str, str]:
        """
        Calculates the next version key for an account without merging.
        e.g.
        First crawl: domain:example.com -> version v1
        Second crawl: domain:example.com:v2 -> version v2
        Third crawl: domain:example.com:v3 -> version v3
        """
        accounts_svc = self._get_accounts_service()
        base_key = f"domain:{domain}"

        # Check if baseline v1 exists
        existing_v1 = accounts_svc.get_account(base_key) or accounts_svc.get_account(domain)
        if not existing_v1:
            return base_key, "v1"

        # Baseline exists, find highest increment
        v_num = 2
        while True:
            candidate_key = f"{base_key}:v{v_num}"
            if accounts_svc.get_account(candidate_key):
                v_num += 1
            else:
                return candidate_key, f"v{v_num}"

    def crawl_domain_with_retries(
        self,
        domain: str,
        scan_depth: str = "standard",
        scanner_type: str = "all",
        enable_subdomains: bool = True,
        custom_ports: Optional[List[int]] = None,
        save_to_database: bool = False,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        last_exception = None
        for attempt in range(max_retries):
            try:
                return self.crawl_domain(
                    domain=domain,
                    scan_depth=scan_depth,
                    scanner_type=scanner_type,
                    enable_subdomains=enable_subdomains,
                    custom_ports=custom_ports,
                    save_to_database=save_to_database,
                )
            except Exception as e:
                last_exception = e
                wait_time = 1.0 * (2 ** attempt)
                logger.warning(
                    f"Crawl attempt {attempt + 1}/{max_retries} failed for domain '{domain}': {e}. Retrying in {wait_time:.1f}s",
                    domain=domain,
                    attempt=attempt + 1,
                    wait_time=wait_time,
                )
                time.sleep(wait_time)

        raise last_exception or RuntimeError(f"Crawl failed for domain '{domain}' after {max_retries} attempts")

    def crawl_domain(
        self,
        domain: str,
        scan_depth: str = "standard",
        scanner_type: str = "all",
        enable_subdomains: bool = True,
        custom_ports: Optional[List[int]] = None,
        save_to_database: bool = False,
    ) -> Dict[str, Any]:
        clean_domain = normalize_domain(domain)
        if not clean_domain:
            raise ValueError("Target domain cannot be empty")

        with logger.span("crawler.recon", domain=clean_domain, scan_depth=scan_depth, scanner_type=scanner_type):
            start_time = time.time()

            # Execute scan via ScannerFactory
            scan_options = {
                "scan_depth": scan_depth,
                "enable_subdomains": enable_subdomains,
                "custom_ports": custom_ports,
                "timeout": self.timeout,
            }
            scan_res = ScannerFactory.run_scan(
                domain=clean_domain,
                scanner_type=scanner_type,
                options=scan_options,
            )

            elapsed_ms = int((time.time() - start_time) * 1000)

            # Determine next account key version without merging
            account_key, version_tag = self._calculate_next_account_version(clean_domain)

            # Build distinct unmerged Account record
            account = Account(
                account_key=account_key,
                version=version_tag,
                domain=clean_domain,
                domains=[clean_domain],
                assets=scan_res.assets,
                ips=scan_res.ips,
                hostnames=scan_res.hostnames,
                ports=scan_res.ports,
                products=scan_res.products,
                cloud_providers=scan_res.cloud_providers,
                signals=scan_res.signals,
            )

            if save_to_database:
                accounts_svc = self._get_accounts_service()
                accounts_svc.save_account(account)

            scan_result = {
                "domain": clean_domain,
                "account_key": account.account_key,
                "version": version_tag,
                "scanner_type": scanner_type,
                "scan_depth": scan_depth,
                "elapsed_ms": elapsed_ms,
                "discovered_hosts": account.hostnames,
                "assets_count": len(account.assets),
                "ips_count": len(account.ips),
                "ports_discovered": account.ports,
                "technologies": account.products,
                "cloud_providers": account.cloud_providers,
                "signals_detected_count": len(account.signals),
                "vulnerabilities_count": len(scan_res.vulnerabilities),
                "vulnerabilities": scan_res.vulnerabilities,
                "cves": scan_res.cves,
                "signals": [s.model_dump() if hasattr(s, "model_dump") else s.dict() for s in account.signals],
                "account": account.model_dump() if hasattr(account, "model_dump") else account.dict(),
            }

            self.writer.cache_scan(clean_domain, scan_result)
            logger.info(
                "Crawler reconnaissance completed",
                domain=clean_domain,
                account_key=account_key,
                version=version_tag,
                scanner_type=scanner_type,
                elapsed_ms=elapsed_ms,
                signals_count=len(account.signals),
            )
            return scan_result

    def handle_crawler_job_scan(
        self,
        job_id: str,
        payload: Dict[str, Any],
        progress_cb: Callable,
    ) -> Dict[str, Any]:
        domains = payload.get("domains", [])
        scan_depth = payload.get("scan_depth", "standard")
        scanner_type = payload.get("scanner_type", "all")
        enable_subdomains = payload.get("enable_subdomains", True)
        custom_ports = payload.get("custom_ports")
        save_to_db = payload.get("save_to_database", True)

        results = []
        total_assets = 0
        total_signals = 0

        for idx, dom in enumerate(domains):
            try:
                res = self.crawl_domain_with_retries(
                    domain=dom,
                    scan_depth=scan_depth,
                    scanner_type=scanner_type,
                    enable_subdomains=enable_subdomains,
                    custom_ports=custom_ports,
                    save_to_database=save_to_db,
                    max_retries=3,
                )
                results.append(res)
                total_assets += res.get("assets_count", 0)
                total_signals += res.get("signals_detected_count", 0)
            except Exception as e:
                logger.error(f"Error in crawler job {job_id} for domain {dom}: {e}")
                results.append({
                    "domain": dom,
                    "error": str(e),
                    "assets_count": 0,
                    "signals_detected_count": 0,
                })

            progress_cb(
                idx + 1,
                len(domains),
                metadata={
                    "assets_discovered_count": total_assets,
                    "signals_detected_count": total_signals,
                    "domains_count": len(domains),
                    "scan_depth": scan_depth,
                    "scanner_type": scanner_type,
                },
                partial_results=results,
            )

        return {
            "results": results,
            "metadata": {
                "assets_discovered_count": total_assets,
                "signals_detected_count": total_signals,
                "domains_count": len(domains),
                "scan_depth": scan_depth,
                "scanner_type": scanner_type,
            },
        }


DomainCrawler = CrawlerService
default_crawler_service = CrawlerService()

default_jobs_service.register_handler("crawler_scan", default_crawler_service.handle_crawler_job_scan)
