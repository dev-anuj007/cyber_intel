from typing import Dict, List, Optional

from src.services.prompts.protocols import IPromptReader
from src.services.prompts.templates import (
    CANONICAL_PROMPTS_DICT,
    get_prompt_template,
)
from src.services.prompts.types import PromptItem


class PromptReader(IPromptReader):
    def __init__(self, memory_store: Optional[Dict[str, PromptItem]] = None):
        if memory_store is not None:
            self._prompts = memory_store
        else:
            self._prompts = {
                f"{p['name']}:{p['version']}": PromptItem.model_validate(p)
                for p in CANONICAL_PROMPTS_DICT
            }

    def list_prompts(self) -> List[PromptItem]:
        return list(self._prompts.values())

    def get_prompt(self, name: str, version: str) -> Optional[PromptItem]:
        key = f"{name}:{version}"
        if key in self._prompts:
            return self._prompts[key]
        for p in self._prompts.values():
            if p.version == version and (p.name == name or not name):
                return p
        template = get_prompt_template(version)
        return PromptItem(
            name=name,
            version=version,
            filename=f"{name}_{version}.txt",
            type="scoring",
            template=template,
        )
