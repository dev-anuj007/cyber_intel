from typing import Any, Dict, List, Optional, Protocol

from pydantic import BaseModel


class PromptRegisterRequest(BaseModel):
    name: str
    version: str
    template: str
    prompt_type: str = "scoring"


class IPromptRepository(Protocol):
    def list_prompts(self) -> List[Dict[str, Any]]: ...

    def get_prompt(self, name: str, version: str) -> Optional[Dict[str, Any]]: ...

    def register_prompt(
        self,
        name: str,
        version: str,
        template: str,
        prompt_type: str = "scoring",
    ) -> Dict[str, Any]: ...

    def delete_prompt(self, name: str, version: str) -> bool: ...


class IPromptService(Protocol):
    def list_prompts(self) -> List[Dict[str, Any]]: ...

    def get_prompt(self, name: str, version: str) -> Optional[Dict[str, Any]]: ...

    def get_template(self, version: str = "v2.0", prompt_type: str = "scoring") -> str: ...

    def register_prompt(
        self,
        name: str,
        version: str,
        template: str,
        prompt_type: str = "scoring",
    ) -> Dict[str, Any]: ...

    def delete_prompt(self, name: str, version: str) -> bool: ...
