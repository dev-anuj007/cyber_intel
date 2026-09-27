from typing import Any, Dict, List, Optional

from src.services.logger.logger_service import BaseLogger
from src.services.prompts.dependencies import (
    PromptServiceDependencyContext,
    get_prompt_dependency_context,
)
from src.services.prompts.protocols import (
    IPromptReader,
    IPromptService,
    IPromptWriter,
)
from src.services.prompts.templates import get_prompt_template
from src.services.prompts.types import RegisterPromptCommand


class PromptService(IPromptService):
    def __init__(self, context: Optional[PromptServiceDependencyContext] = None):
        ctx = context or get_prompt_dependency_context()
        self._reader: IPromptReader = ctx.reader
        self._writer: IPromptWriter = ctx.writer
        self._logger: BaseLogger = ctx.logger

    def list_prompts(self) -> List[Dict[str, Any]]:
        with self._logger.span("prompts.list"):
            return self._reader.list_prompts()

    def get_prompt(self, name: str, version: str) -> Optional[Dict[str, Any]]:
        with self._logger.span("prompts.get", prompt_name=name, version=version):
            return self._reader.get_prompt(name=name, version=version)

    def get_template(self, version: str = "v2.0", prompt_type: str = "scoring") -> str:
        prompt = self.get_prompt(name="account_scoring", version=version)
        if prompt and prompt.get("template"):
            return prompt["template"]
        return get_prompt_template(version)

    def register_prompt(
        self,
        name: str,
        version: str,
        template: str,
        prompt_type: str = "scoring",
    ) -> Dict[str, Any]:
        with self._logger.span("prompts.register", prompt_name=name, version=version):
            command = RegisterPromptCommand(
                name=name,
                version=version,
                template=template,
                prompt_type=prompt_type,
            )
            return self._writer.register_prompt(command)

    def delete_prompt(self, name: str, version: str) -> bool:
        with self._logger.span("prompts.delete", prompt_name=name, version=version):
            return self._writer.delete_prompt(name=name, version=version)


default_prompt_service = PromptService()
