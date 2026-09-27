from typing import List, Optional, Protocol, runtime_checkable

from src.services.prompts.types import PromptItem, RegisterPromptCommand


@runtime_checkable
class IPromptReader(Protocol):
    def list_prompts(self) -> List[PromptItem]: ...

    def get_prompt(self, name: str, version: str) -> Optional[PromptItem]: ...


@runtime_checkable
class IPromptWriter(Protocol):
    def register_prompt(self, command: RegisterPromptCommand) -> PromptItem: ...

    def delete_prompt(self, name: str, version: str) -> bool: ...


@runtime_checkable
class IPromptRepository(Protocol):
    def list_prompts(self) -> List[PromptItem]: ...

    def get_prompt(self, name: str, version: str) -> Optional[PromptItem]: ...

    def register_prompt(
        self,
        name: str,
        version: str,
        template: str,
        prompt_type: str = "scoring",
        description: Optional[str] = None,
    ) -> PromptItem: ...

    def delete_prompt(self, name: str, version: str) -> bool: ...


@runtime_checkable
class IPromptService(Protocol):
    def list_prompts(self) -> List[PromptItem]: ...

    def get_prompt(self, name: str, version: str) -> Optional[PromptItem]: ...

    def get_template(
        self, version: str = "v2.0", prompt_type: str = "scoring"
    ) -> str: ...

    def register_prompt(
        self,
        name: str,
        version: str,
        template: str,
        prompt_type: str = "scoring",
        description: Optional[str] = None,
    ) -> PromptItem: ...

    def delete_prompt(self, name: str, version: str) -> bool: ...
