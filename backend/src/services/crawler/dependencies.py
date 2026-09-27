from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

from src.services.accounts.dependencies import get_accounts_service
from src.services.accounts.protocols import IAccountsService
from src.services.crawler.internals.scanners.factory import ScannerFactory
from src.services.crawler.internals.versioning import AccountVersionCalculator
from src.services.crawler.protocols import ICrawlerService
from src.services.logger.logger_service import BaseLogger, get_logger


if TYPE_CHECKING:
    from src.services.crawler.crawler_service import CrawlerService


@dataclass
class CrawlerServiceDependencyContext:
    accounts_service: IAccountsService
    logger: BaseLogger
    scanner_factory: Any = ScannerFactory
    version_calculator: Any = AccountVersionCalculator
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
    def __getattr__(self, name: str) -> Any:
        return getattr(get_crawler_service(), name)


default_crawler_service: ICrawlerService = _LazyCrawlerServiceProxy()  # type: ignore

