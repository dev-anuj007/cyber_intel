from typing import Any, Dict, Optional

from src.services.prompts.protocols import IPromptWriter
from src.services.prompts.templates import CANONICAL_PROMPTS_LIST
from src.services.prompts.types import RegisterPromptCommand


class PromptWriter(IPromptWriter):
    def __init__(self, memory_store: Optional[Dict[str, Dict[str, Any]]] = None):
        self._prompts = memory_store if memory_store is not None else {
            f"{p['name']}:{p['version']}": p.copy() for p in CANONICAL_PROMPTS_LIST
        }

    def register_prompt(self, command: RegisterPromptCommand) -> Dict[str, Any]:
        item = {
            "name": command.name,
            "version": command.version,
            "filename": f"{command.name}_{command.version}.txt",
            "type": command.prompt_type,
            "template": command.template,
        }
        self._prompts[f"{command.name}:{command.version}"] = item
        return item

    def delete_prompt(self, name: str, version: str) -> bool:
        key = f"{name}:{version}"
        if key in self._prompts:
            del self._prompts[key]
            return True
        for k, p in list(self._prompts.items()):
            if p.get("version") == version and (p.get("name") == name or not name):
                del self._prompts[k]
                return True
        return False
