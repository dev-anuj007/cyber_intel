from typing import Any, Dict, List, Optional

from src.services.prompts.protocols import IPromptReader
from src.services.prompts.templates import CANONICAL_PROMPTS_LIST, get_prompt_template


class PromptReader(IPromptReader):
    def __init__(self, memory_store: Optional[Dict[str, Dict[str, Any]]] = None):
        self._prompts = memory_store if memory_store is not None else {
            f"{p['name']}:{p['version']}": p.copy() for p in CANONICAL_PROMPTS_LIST
        }

    def list_prompts(self) -> List[Dict[str, Any]]:
        return list(self._prompts.values())

    def get_prompt(self, name: str, version: str) -> Optional[Dict[str, Any]]:
        key = f"{name}:{version}"
        if key in self._prompts:
            return self._prompts[key]
        for p in self._prompts.values():
            if p.get("version") == version:
                return p
        template = get_prompt_template(version)
        return {
            "name": name,
            "version": version,
            "filename": f"{name}_{version}.txt",
            "type": "scoring",
            "template": template,
        }
