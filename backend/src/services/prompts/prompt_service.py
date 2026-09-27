from typing import List, Optional

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
from src.services.prompts.types import PromptItem, RegisterPromptCommand


class PromptService(IPromptService):
    def __init__(
        self, context: Optional[PromptServiceDependencyContext] = None
    ) -> None:
        self.context: PromptServiceDependencyContext = (
            context or get_prompt_dependency_context()
        )
        self._reader: IPromptReader = self.context.reader
        self._writer: IPromptWriter = self.context.writer
        self._logger: BaseLogger = self.context.logger

    def list_prompts(self) -> List[PromptItem]:
        with self._logger.span("prompts.list"):
            return self._reader.list_prompts()

    def get_prompt(self, name: str, version: str) -> Optional[PromptItem]:
        with self._logger.span("prompts.get", prompt_name=name, version=version):
            return self._reader.get_prompt(name=name, version=version)

    def get_template(self, version: str = "v2.0", prompt_type: str = "scoring") -> str:
        prompt = self.get_prompt(name="account_scoring", version=version)
        if prompt and prompt.template:
            return prompt.template
        return get_prompt_template(version)

    def register_prompt(
        self,
        name: str,
        version: str,
        template: str,
        prompt_type: str = "scoring",
        description: Optional[str] = None,
    ) -> PromptItem:
        with self._logger.span("prompts.register", prompt_name=name, version=version):
            command = RegisterPromptCommand(
                name=name,
                version=version,
                template=template,
                prompt_type=prompt_type,
                description=description,
            )
            return self._writer.register_prompt(command)

    def delete_prompt(self, name: str, version: str) -> bool:
        with self._logger.span("prompts.delete", prompt_name=name, version=version):
            return self._writer.delete_prompt(name=name, version=version)
