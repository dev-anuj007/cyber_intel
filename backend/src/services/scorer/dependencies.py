from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Optional, Union

from fastapi import Depends

from src.core.exceptions import InvalidInputError
from src.services.auth.dependencies import get_current_user_optional
from src.services.prompts.protocols import IPromptService
from src.services.scorer.internals.repositories.reader import ScoreReader
from src.services.scorer.internals.repositories.writer import ScoreWriter
from src.services.scorer.protocols import IScoreReader, IScoreWriter, IScorerService


@dataclass(frozen=True)
class ScorerServiceDependencyContext:
    reader: IScoreReader
    writer: IScoreWriter
    accounts_service: Optional[Any] = None
    db_path: Optional[Union[Path, str]] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    prompt_version: Optional[str] = None
    trace_dir: Optional[Union[Path, str]] = None
    prompt_service: Optional[IPromptService] = None


def get_scorer_dependency_context(
    db_path: Optional[Union[Path, str]] = None,
    reader: Optional[IScoreReader] = None,
    writer: Optional[IScoreWriter] = None,
    accounts_service: Optional[Any] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    prompt_version: Optional[str] = None,
    trace_dir: Optional[Union[Path, str]] = None,
    prompt_service: Optional[IPromptService] = None,
) -> ScorerServiceDependencyContext:
    return ScorerServiceDependencyContext(
        reader=reader if reader is not None else ScoreReader(),
        writer=writer if writer is not None else ScoreWriter(),
        accounts_service=accounts_service,
        db_path=db_path,
        api_key=api_key,
        model=model,
        prompt_version=prompt_version,
        trace_dir=trace_dir,
        prompt_service=prompt_service,
    )


def create_scorer_service(
    context: Optional[ScorerServiceDependencyContext] = None,
    **kwargs: Any,
) -> IScorerService:
    from src.services.scorer.scorer_service import ScorerService

    if context is None:
        context = get_scorer_dependency_context(**kwargs)
    return ScorerService(context=context)


_default_scorer_service: Optional[IScorerService] = None


def get_scorer_service() -> IScorerService:
    global _default_scorer_service
    if _default_scorer_service is None:
        _default_scorer_service = create_scorer_service()
    return _default_scorer_service


class _LazyScorerServiceProxy:
    def __getattr__(self, name: str) -> Any:
        return getattr(get_scorer_service(), name)


default_scorer_service: IScorerService = _LazyScorerServiceProxy()  # type: ignore



def get_user_scorer(
    current_user: Optional[dict] = Depends(get_current_user_optional),
) -> IScorerService:
    api_key = current_user.get("gemini_api_key") if current_user else None
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise InvalidInputError(
            message="Gemini API key not configured. Please open Profile settings and add your Google Gemini API key to run AI scoring.",
            code="MISSING_GEMINI_API_KEY",
        )
    return create_scorer_service(api_key=api_key)



