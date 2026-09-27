from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, Type

from src.services.accounts.dependencies import get_accounts_service
from src.services.accounts.protocols import IAccountsService
from src.services.crawler.internals.scanners.factory import ScannerFactory
from src.services.crawler.internals.versioning import AccountVersionCalculator
from src.services.crawler.protocols import ICrawlerService
from src.services.logger.logger_service import BaseLogger, get_logger

if TYPE_CHECKING:
    from src.services.crawler.types import (
        CrawlerBatchResult,
        CrawlerRunRequest,
        CrawlerScanRequest,
        CrawlerScanResult,
    )


@dataclass
class CrawlerServiceDependencyContext:
    accounts_service: IAccountsService
    logger: BaseLogger
    scanner_factory: Type[ScannerFactory] = ScannerFactory
    version_calculator: Type[AccountVersionCalculator] = AccountVersionCalculator
    timeout: float = 0.8


def get_crawler_dependency_context(
    accounts_service: Optional[IAccountsService] = None,
    logger: Optional[BaseLogger] = None,
    timeout: float = 0.8,
    db_path: Optional[Any] = None,
) -> CrawlerServiceDependencyContext:
    return CrawlerServiceDependencyContext(
        accounts_service=accounts_service or get_accounts_service(),
        logger=logger or get_logger("services.crawler"),
        timeout=timeout,
    )


_default_crawler_service: Optional[ICrawlerService] = None


def get_crawler_service() -> ICrawlerService:
    global _default_crawler_service
    if _default_crawler_service is None:
        _default_crawler_service = create_crawler_service()
    return _default_crawler_service


def create_crawler_service(
    context: Optional[CrawlerServiceDependencyContext] = None,
) -> ICrawlerService:
    from src.services.crawler.crawler_service import CrawlerService

    return CrawlerService(context=context or get_crawler_dependency_context())


class _LazyCrawlerServiceProxy:
    def crawl_domain(
        self,
        request: "CrawlerScanRequest",
    ) -> "CrawlerScanResult":
        return get_crawler_service().crawl_domain(request)

    def scan_domain(
        self,
        request: "CrawlerScanRequest",
    ) -> "CrawlerScanResult":
        return get_crawler_service().scan_domain(request)

    async def crawl_domain_async(
        self,
        request: "CrawlerScanRequest",
    ) -> "CrawlerScanResult":
        return await get_crawler_service().crawl_domain_async(request)

    async def scan_domain_async(
        self,
        request: "CrawlerScanRequest",
    ) -> "CrawlerScanResult":
        return await get_crawler_service().scan_domain_async(request)

    def crawl_domain_with_retries(
        self,
        request: "CrawlerScanRequest",
        max_retries: int = 3,
    ) -> "CrawlerScanResult":
        return get_crawler_service().crawl_domain_with_retries(
            request, max_retries=max_retries
        )

    async def crawl_domain_with_retries_async(
        self,
        request: "CrawlerScanRequest",
        max_retries: int = 3,
    ) -> "CrawlerScanResult":
        return await get_crawler_service().crawl_domain_with_retries_async(
            request, max_retries=max_retries
        )

    def handle_crawler_job_scan(
        self,
        job_id: str,
        request: "CrawlerRunRequest",
        progress_cb: Any,
    ) -> "CrawlerBatchResult":
        return get_crawler_service().handle_crawler_job_scan(
            job_id, request, progress_cb
        )

    async def handle_crawler_job_scan_async(
        self,
        job_id: str,
        request: "CrawlerRunRequest",
        progress_cb: Any,
    ) -> "CrawlerBatchResult":
        return await get_crawler_service().handle_crawler_job_scan_async(
            job_id, request, progress_cb
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(get_crawler_service(), name)


default_crawler_service: ICrawlerService = _LazyCrawlerServiceProxy()  # type: ignore
