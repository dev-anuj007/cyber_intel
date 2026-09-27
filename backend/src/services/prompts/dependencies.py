from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Optional

from src.services.logger.logger_service import BaseLogger, get_logger
from src.services.prompts.internals.repositories.reader import PromptReader
from src.services.prompts.internals.repositories.writer import PromptWriter
from src.services.prompts.protocols import (
    IPromptReader,
    IPromptService,
    IPromptWriter,
)
from src.services.prompts.types import PromptItem


@dataclass
class PromptServiceDependencyContext:
    reader: IPromptReader
    writer: IPromptWriter
    logger: BaseLogger


def get_prompt_dependency_context(
    reader: Optional[IPromptReader] = None,
    writer: Optional[IPromptWriter] = None,
    logger: Optional[BaseLogger] = None,
) -> PromptServiceDependencyContext:
    shared_store: Optional[Dict[str, PromptItem]] = None
    if reader is None and writer is None:
        from src.services.prompts.templates import CANONICAL_PROMPTS_DICT

        shared_store = {
            f"{p['name']}:{p['version']}": PromptItem.model_validate(p)
            for p in CANONICAL_PROMPTS_DICT
        }
    return PromptServiceDependencyContext(
        reader=reader or PromptReader(memory_store=shared_store),
        writer=writer or PromptWriter(memory_store=shared_store),
        logger=logger or get_logger("services.prompts"),
    )


@lru_cache()
def get_prompt_service() -> IPromptService:
    from src.services.prompts.prompt_service import PromptService

    return PromptService()


def create_prompt_service(
    context: Optional[PromptServiceDependencyContext] = None,
    reader: Optional[IPromptReader] = None,
    writer: Optional[IPromptWriter] = None,
    logger: Optional[BaseLogger] = None,
) -> IPromptService:
    from src.services.prompts.prompt_service import PromptService

    if context is not None:
        return PromptService(context)
    return PromptService(
        get_prompt_dependency_context(reader=reader, writer=writer, logger=logger)
    )


class _LazyPromptServiceProxy:
    def __getattr__(self, name: str) -> Any:
        return getattr(get_prompt_service(), name)


default_prompt_service: IPromptService = _LazyPromptServiceProxy()  # type: ignore
