from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

from src.services.eval.internals.repositories.reader import EvalReader
from src.services.eval.internals.repositories.writer import EvalWriter
from src.services.eval.protocols import IEvalReader, IEvalService, IEvalWriter
from src.services.prompts.protocols import IPromptService


@dataclass(frozen=True)
class EvalServiceDependencyContext:
    reader: IEvalReader
    writer: IEvalWriter
    prompt_service: Optional[IPromptService] = None
    evals_dir: Optional[Path] = None
    db_path: Optional[Union[Path, str]] = None


def get_eval_dependency_context(
    db_path: Optional[Union[Path, str]] = None,
    reader: Optional[IEvalReader] = None,
    writer: Optional[IEvalWriter] = None,
    prompt_service: Optional[IPromptService] = None,
    evals_dir: Optional[Path] = None,
) -> EvalServiceDependencyContext:
    return EvalServiceDependencyContext(
        reader=reader if reader is not None else EvalReader(),
        writer=writer if writer is not None else EvalWriter(),
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


class _LazyEvalServiceProxy:
    def __getattr__(self, name: str) -> Any:
        return getattr(get_eval_service(), name)


default_eval_service: IEvalService = _LazyEvalServiceProxy()  # type: ignore




