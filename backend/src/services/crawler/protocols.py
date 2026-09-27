from typing import Callable, Protocol, runtime_checkable

from src.services.crawler.types import (
    CrawlerBatchResult,
    CrawlerRunRequest,
    CrawlerScanRequest,
    CrawlerScanResult,
)


@runtime_checkable
class ICrawlerService(Protocol):
    def crawl_domain(
        self,
        request: CrawlerScanRequest,
    ) -> CrawlerScanResult: ...

    def scan_domain(
        self,
        request: CrawlerScanRequest,
    ) -> CrawlerScanResult: ...

    async def crawl_domain_async(
        self,
        request: CrawlerScanRequest,
    ) -> CrawlerScanResult: ...

    async def scan_domain_async(
        self,
        request: CrawlerScanRequest,
    ) -> CrawlerScanResult: ...

    def crawl_domain_with_retries(
        self,
        request: CrawlerScanRequest,
        max_retries: int = 3,
    ) -> CrawlerScanResult: ...

    async def crawl_domain_with_retries_async(
        self,
        request: CrawlerScanRequest,
        max_retries: int = 3,
    ) -> CrawlerScanResult: ...

    def handle_crawler_job_scan(
        self,
        job_id: str,
        request: CrawlerRunRequest,
        progress_cb: Callable[..., None],
    ) -> CrawlerBatchResult: ...

    async def handle_crawler_job_scan_async(
        self,
        job_id: str,
        request: CrawlerRunRequest,
        progress_cb: Callable[..., None],
    ) -> CrawlerBatchResult: ...
