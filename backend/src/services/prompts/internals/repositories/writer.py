from typing import Dict, Optional

from src.services.prompts.protocols import IPromptWriter
from src.services.prompts.templates import CANONICAL_PROMPTS_DICT
from src.services.prompts.types import PromptItem, RegisterPromptCommand


class PromptWriter(IPromptWriter):
    def __init__(self, memory_store: Optional[Dict[str, PromptItem]] = None):
        if memory_store is not None:
            self._prompts = memory_store
        else:
            self._prompts = {
                f"{p['name']}:{p['version']}": PromptItem.model_validate(p)
                for p in CANONICAL_PROMPTS_DICT
            }

    def register_prompt(self, command: RegisterPromptCommand) -> PromptItem:
        item = PromptItem(
            name=command.name,
            version=command.version,
            filename=f"{command.name}_{command.version}.txt",
            type=command.prompt_type,
            template=command.template,
            description=command.description,
        )
        self._prompts[f"{command.name}:{command.version}"] = item
        return item

    def delete_prompt(self, name: str, version: str) -> bool:
        key = f"{name}:{version}"
        if key in self._prompts:
            del self._prompts[key]
            return True
        for k, p in list(self._prompts.items()):
            if p.version == version and (p.name == name or not name):
                del self._prompts[k]
                return True
        return False
