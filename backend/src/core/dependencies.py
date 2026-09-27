from src.services.accounts.dependencies import (
    default_accounts_service,
    get_accounts_service,
)
from src.services.aggregator.dependencies import get_aggregator_service
from src.services.auth.dependencies import (
    get_auth_service,
    get_current_user,
    get_current_user_optional,
)
from src.services.crawler.dependencies import get_crawler_service
from src.services.database.dependencies import get_database_service, get_db_service
from src.services.eval.dependencies import get_eval_service
from src.services.eval.eval_service import default_eval_service
from src.services.jobs.dependencies import get_jobs_service
from src.services.logger.logger_service import get_logger
from src.services.logger.dependencies import get_app_logger, get_logger_service
from src.services.prompts.dependencies import get_prompt_service
from src.services.scorer.dependencies import get_scorer_service, get_user_scorer
from src.services.scorer.scorer_service import default_scorer_service

logger = get_logger("core.dependencies")


def init_core_services() -> None:
    try:
        default_scorer_service.set_accounts_service(default_accounts_service)
        from src.services.crawler.types import CrawlerRunRequest

        jobs_service = get_jobs_service()
        jobs_service.register_handler(
            "crawler_scan",
            lambda job_id, metadata, progress_cb: get_crawler_service().handle_crawler_job_scan(
                job_id,
                CrawlerRunRequest(**metadata) if isinstance(metadata, dict) else metadata,
                progress_cb,
            ),
        )
        jobs_service.register_handler("eval_run", default_eval_service.handle_eval_job)
        jobs_service.register_handler("eval_compare", default_eval_service.handle_eval_compare_job)
        logger.info("Core microservices initialized and wired")
    except Exception as e:
        logger.warning(f"Core microservice wireup error: {e}")


__all__ = [
    "init_core_services",
    "get_database_service",
    "get_db_service",
    "get_accounts_service",
    "get_aggregator_service",
    "get_crawler_service",
    "get_eval_service",
    "get_auth_service",
    "get_current_user",
    "get_current_user_optional",
    "get_scorer_service",
    "get_user_scorer",
    "get_logger_service",
    "get_app_logger",
    "get_prompt_service",
    "get_jobs_service",
]
