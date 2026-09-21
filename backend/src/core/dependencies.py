from src.services.accounts import AccountsService, default_accounts_service
from src.services.aggregator import AggregatorService, default_aggregator_service
from src.services.auth import AuthService, default_auth_service
from src.services.crawler import CrawlerService, default_crawler_service
from src.services.database import DatabaseService, default_database_service
from src.services.eval import EvalService, default_eval_service
from src.services.logger import BaseLogger, LoggerService, default_logger_service, get_logger
from src.services.scorer import ScorerService, default_scorer_service

logger = get_logger("core.dependencies")


def init_core_services() -> None:
    try:
        default_scorer_service.set_accounts_service(default_accounts_service)
        default_crawler_service.set_accounts_service(default_accounts_service)
        logger.info("Core microservices initialized and wired")
    except Exception as e:
        logger.warning(f"Core microservice wireup error: {e}")


def get_database_service() -> DatabaseService:
    return default_database_service


def get_accounts_service() -> AccountsService:
    return default_accounts_service


def get_aggregator_service() -> AggregatorService:
    return default_aggregator_service


def get_crawler_service() -> CrawlerService:
    return default_crawler_service


def get_eval_service() -> EvalService:
    return default_eval_service


def get_auth_service() -> AuthService:
    return default_auth_service


def get_scorer_service() -> ScorerService:
    return default_scorer_service


def get_logger_service() -> LoggerService:
    return default_logger_service


def get_app_logger(name: str = "app") -> BaseLogger:
    return default_logger_service.get_logger(name)
