from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.services.database.database_service import DatabaseService
from src.services.database.dependencies import default_database_service
from src.services.database.protocols import IDatabaseService
from src.services.eval.internals.repositories.reader import EvalReader
from src.services.eval.internals.repositories.writer import EvalWriter
from src.services.eval.protocols import IEvalReader, IEvalService, IEvalWriter
from src.services.eval.types import (
    ComparePromptsCommand,
    EvalCompareResult,
    EvalHistoryItem,
    EvalRunResult,
    RunEvalCommand,
)
from src.services.logger.internals.base_logger import BaseLogger
from src.services.logger.logger_service import get_logger
from src.services.prompts.protocols import IPromptService


@dataclass(frozen=True)
class EvalServiceDependencyContext:
    reader: IEvalReader
    writer: IEvalWriter
    db_service: IDatabaseService
    logger: BaseLogger
    prompt_service: Optional[IPromptService] = None
    evals_dir: Optional[Path] = None
    db_path: Optional[Union[Path, str]] = None


def get_eval_dependency_context(
    db_path: Optional[Union[Path, str]] = None,
    db_service: Optional[IDatabaseService] = None,
    reader: Optional[IEvalReader] = None,
    writer: Optional[IEvalWriter] = None,
    prompt_service: Optional[IPromptService] = None,
    evals_dir: Optional[Path] = None,
    logger: Optional[BaseLogger] = None,
) -> EvalServiceDependencyContext:
    resolved_db_service: IDatabaseService = db_service or (
        DatabaseService(db_path=Path(db_path))
        if db_path is not None
        else default_database_service
    )
    return EvalServiceDependencyContext(
        reader=reader if reader is not None else EvalReader(),
        writer=writer if writer is not None else EvalWriter(),
        db_service=resolved_db_service,
        logger=logger or get_logger("services.eval"),
        prompt_service=prompt_service,
        evals_dir=evals_dir,
        db_path=db_path,
    )


def create_eval_service(
    context: Optional[EvalServiceDependencyContext] = None,
    **kwargs: Any,
) -> IEvalService:
    from src.services.eval.eval_service import EvalService

    if context is None:
        context = get_eval_dependency_context(**kwargs)
    return EvalService(context=context)


_default_eval_service: Optional[IEvalService] = None


def get_eval_service() -> IEvalService:
    global _default_eval_service
    if _default_eval_service is None:
        _default_eval_service = create_eval_service()
    return _default_eval_service


class _LazyEvalServiceProxy(IEvalService):
    def list_prompts(self) -> List[Any]:
        return get_eval_service().list_prompts()

    def get_default_dataset(self) -> List[Dict[str, Any]]:
        return get_eval_service().get_default_dataset()

    def run_eval(self, command: RunEvalCommand) -> EvalRunResult:
        return get_eval_service().run_eval(command)

    def compare_prompts(self, command: ComparePromptsCommand) -> EvalCompareResult:
        return get_eval_service().compare_prompts(command)

    def list_history(self) -> List[EvalHistoryItem]:
        return get_eval_service().list_history()

    def get_result_file(self, filename: str) -> Optional[Dict[str, Any]]:
        return get_eval_service().get_result_file(filename)

    def handle_eval_job(
        self,
        job_id: str,
        payload: Dict[str, Any],
        progress_callback: Optional[Any] = None,
    ) -> Dict[str, Any]:
        return get_eval_service().handle_eval_job(job_id, payload, progress_callback)

    def handle_eval_compare_job(
        self,
        job_id: str,
        payload: Dict[str, Any],
        progress_callback: Optional[Any] = None,
    ) -> Dict[str, Any]:
        return get_eval_service().handle_eval_compare_job(
            job_id, payload, progress_callback
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(get_eval_service(), name)


default_eval_service: IEvalService = _LazyEvalServiceProxy()
