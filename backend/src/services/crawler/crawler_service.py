import asyncio
import time
from typing import Callable, Optional, Tuple

from src.services.accounts.protocols import IAccountsService
from src.services.accounts.types import Account
from src.services.aggregator.internals.domain_utils import is_valid_account_domain, normalize_domain
from src.services.crawler.dependencies import (
    CrawlerServiceDependencyContext,
    get_crawler_dependency_context,
)
from src.services.crawler.internals.dns import is_domain_resolvable
from src.services.crawler.internals.scanners.types import ScannerEngineOptions
from src.services.crawler.protocols import ICrawlerService
from src.services.crawler.types import (
    CrawlerBatchMetadata,
    CrawlerBatchResult,
    CrawlerRunRequest,
    CrawlerScanRequest,
    CrawlerScanResult,
)


class CrawlerService(ICrawlerService):
    def __init__(self, context: Optional[CrawlerServiceDependencyContext] = None):
        self._context = context or get_crawler_dependency_context()

    def scan_domain(self, request: CrawlerScanRequest) -> CrawlerScanResult:
        return self.crawl_domain(request)

    async def scan_domain_async(self, request: CrawlerScanRequest) -> CrawlerScanResult:
        return await self.crawl_domain_async(request)

    def crawl_domain(self, request: CrawlerScanRequest) -> CrawlerScanResult:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, self.crawl_domain_async(request)).result()
        return asyncio.run(self.crawl_domain_async(request))

    async def crawl_domain_async(self, request: CrawlerScanRequest) -> CrawlerScanResult:
        clean_domain = normalize_domain(request.domain)

        if not clean_domain:
            raise ValueError("Target domain cannot be empty")
        if not is_valid_account_domain(clean_domain):
            raise ValueError(f"Invalid domain format: '{clean_domain}'")
        if not await asyncio.to_thread(self._is_domain_resolvable, clean_domain):
            raise ValueError(f"Domain '{clean_domain}' could not be resolved via DNS or does not exist")

        with self._context.logger.span(
            "crawler.recon",
            domain=clean_domain,
            scan_depth=request.scan_depth,
            scanner_type=request.scanner_type,
        ):
            start_time = time.time()

            scan_options = ScannerEngineOptions(
                scan_depth=request.scan_depth,
                enable_subdomains=request.enable_subdomains,
                custom_ports=request.custom_ports,
                timeout=self._context.timeout,
            )

            if hasattr(self._context.scanner_factory, "run_scan_async"):
                scan_res = await self._context.scanner_factory.run_scan_async(
                    domain=clean_domain,
                    scanner_type=request.scanner_type,
                    options=scan_options,
                    logger=self._context.logger,
                )
            else:
                scan_res = await asyncio.to_thread(
                    self._context.scanner_factory.run_scan,
                    clean_domain,
                    request.scanner_type,
                    scan_options,
                    self._context.logger,
                )

            elapsed_ms = int((time.time() - start_time) * 1000)
            account_key, version_tag = await asyncio.to_thread(self._calculate_next_account_version, clean_domain)

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

            if request.save_to_database:
                await asyncio.to_thread(self._context.accounts_service.save_account, account)

            account_signals = [s.model_dump() if hasattr(s, "model_dump") else s.dict() for s in account.signals]
            account_dict = account.model_dump() if hasattr(account, "model_dump") else account.dict()

            scan_result = CrawlerScanResult(
                domain=clean_domain,
                account_key=account.account_key,
                version=version_tag,
                scanner_type=request.scanner_type,
                scan_depth=request.scan_depth,
                elapsed_ms=elapsed_ms,
                discovered_hosts=account.hostnames,
                assets_count=len(account.assets),
                ips_count=len(account.ips),
                ports_discovered=account.ports,
                technologies=account.products,
                cloud_providers=account.cloud_providers,
                signals_detected_count=len(account.signals),
                vulnerabilities_count=len(scan_res.vulnerabilities),
                vulnerabilities=scan_res.vulnerabilities,
                cves=scan_res.cves,
                signals=account_signals,
                account=account_dict,
            )

            self._context.logger.info(
                "Crawler reconnaissance completed",
                domain=clean_domain,
                account_key=account_key,
                version=version_tag,
                scanner_type=request.scanner_type,
                elapsed_ms=elapsed_ms,
                signals_count=len(account.signals),
            )
            return scan_result

    def crawl_domain_with_retries(
        self,
        request: CrawlerScanRequest,
        max_retries: int = 3,
    ) -> CrawlerScanResult:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(
                    asyncio.run,
                    self.crawl_domain_with_retries_async(request, max_retries),
                ).result()
        return asyncio.run(self.crawl_domain_with_retries_async(request, max_retries))

    async def crawl_domain_with_retries_async(
        self,
        request: CrawlerScanRequest,
        max_retries: int = 3,
    ) -> CrawlerScanResult:
        last_exception = None
        for attempt in range(max_retries):
            try:
                return await self.crawl_domain_async(request)
            except ValueError:
                raise
            except Exception as e:
                last_exception = e
                wait_time = 1.0 * (2**attempt)
                log_msg = (
                    f"Crawl attempt {attempt + 1}/{max_retries} failed for domain "
                    f"'{request.domain}': {e}. Retrying in {wait_time:.1f}s"
                )
                self._context.logger.warning(
                    log_msg,
                    domain=request.domain,
                    attempt=attempt + 1,
                    wait_time=wait_time,
                )
                await asyncio.sleep(wait_time)

        err_msg = f"Crawl failed for domain '{request.domain}' after {max_retries} attempts"
        raise last_exception or RuntimeError(err_msg)

    def handle_crawler_job_scan(
        self,
        job_id: str,
        request: CrawlerRunRequest,
        progress_cb: Callable[..., None],
    ) -> CrawlerBatchResult:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(
                    asyncio.run,
                    self.handle_crawler_job_scan_async(job_id, request, progress_cb),
                ).result()
        return asyncio.run(self.handle_crawler_job_scan_async(job_id, request, progress_cb))

    async def handle_crawler_job_scan_async(
        self,
        job_id: str,
        request: CrawlerRunRequest,
        progress_cb: Callable[..., None],
    ) -> CrawlerBatchResult:
        results = []
        total_assets = 0
        total_signals = 0

        for idx, dom in enumerate(request.domains):
            try:
                domain_scan_req = CrawlerScanRequest(
                    domain=dom,
                    scan_depth=request.scan_depth,
                    scanner_type=request.scanner_type,
                    enable_subdomains=request.enable_subdomains,
                    custom_ports=request.custom_ports,
                    save_to_database=request.save_to_database,
                )
                scan_res = await self.crawl_domain_with_retries_async(
                    domain_scan_req,
                    max_retries=3,
                )
                results.append(scan_res.model_dump())
                total_assets += scan_res.assets_count
                total_signals += scan_res.signals_detected_count
            except Exception as e:
                self._context.logger.error(f"Error in crawler job {job_id} for domain {dom}: {e}")
                results.append(
                    {
                        "domain": dom,
                        "error": str(e),
                        "assets_count": 0,
                        "signals_detected_count": 0,
                    }
                )

            progress_cb(
                idx + 1,
                len(request.domains),
                metadata={
                    "assets_discovered_count": total_assets,
                    "signals_detected_count": total_signals,
                    "domains_count": len(request.domains),
                    "scan_depth": request.scan_depth,
                    "scanner_type": request.scanner_type,
                },
                partial_results=results,
            )

        return CrawlerBatchResult(
            results=results,
            metadata=CrawlerBatchMetadata(
                assets_discovered_count=total_assets,
                signals_detected_count=total_signals,
                domains_count=len(request.domains),
                scan_depth=request.scan_depth,
                scanner_type=request.scanner_type,
            ),
        )

    def set_accounts_service(self, accounts_service: IAccountsService) -> None:
        self._context.accounts_service = accounts_service

    def _calculate_next_account_version(self, domain: str) -> Tuple[str, str]:
        return self._context.version_calculator.calculate_next_version(
            self._context.accounts_service,
            domain,
        )

    def _is_domain_resolvable(self, domain: str) -> bool:
        return is_domain_resolvable(domain)
