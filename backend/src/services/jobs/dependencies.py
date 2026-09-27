from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Optional

from src.services.jobs.internals.repositories.reader import JobsReader
from src.services.jobs.internals.repositories.writer import JobsWriter
from src.services.jobs.protocols import (
    IJobDispatcher,
    IJobsReader,
    IJobsService,
    IJobsWriter,
)
from src.services.logger.logger_service import BaseLogger, get_logger


if TYPE_CHECKING:
    from src.services.jobs.jobs_service import JobsService


@dataclass
class JobsServiceDependencyContext:
    reader: IJobsReader
    writer: IJobsWriter
    logger: BaseLogger
    dispatcher: Optional[IJobDispatcher] = None


def get_jobs_dependency_context(
    db_path: Optional[Any] = None,
    reader: Optional[IJobsReader] = None,
    writer: Optional[IJobsWriter] = None,
    logger: Optional[BaseLogger] = None,
    dispatcher: Optional[IJobDispatcher] = None,
) -> JobsServiceDependencyContext:
    return JobsServiceDependencyContext(
        reader=reader or JobsReader(db_path=db_path),
        writer=writer or JobsWriter(db_path=db_path),
        logger=logger or get_logger("services.jobs"),
        dispatcher=dispatcher,
    )


@lru_cache()
def get_jobs_service() -> IJobsService:
    from src.services.jobs.jobs_service import JobsService

    return JobsService()


def create_jobs_service(
    context: Optional[JobsServiceDependencyContext] = None,
    db_path: Optional[Any] = None,
    reader: Optional[IJobsReader] = None,
    writer: Optional[IJobsWriter] = None,
    dispatcher: Optional[IJobDispatcher] = None,
) -> IJobsService:
    from src.services.jobs.jobs_service import JobsService

    return JobsService(
        context
        or get_jobs_dependency_context(
            db_path=db_path,
            reader=reader,
            writer=writer,
            dispatcher=dispatcher,
        )
    )


class _LazyJobsServiceProxy:
    def __getattr__(self, name: str) -> Any:
        return getattr(get_jobs_service(), name)


default_jobs_service: IJobsService = _LazyJobsServiceProxy()  # type: ignore

