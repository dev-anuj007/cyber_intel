from typing import Any, Dict, List, Optional

from src.services.prompts.prompt_types import IPromptRepository
from src.services.prompts.templates import CANONICAL_PROMPTS_LIST, get_prompt_template


class LocalPromptRepository(IPromptRepository):
    def __init__(self):
        self._prompts = {f"{p['name']}:{p['version']}": p.copy() for p in CANONICAL_PROMPTS_LIST}

    def list_prompts(self) -> List[Dict[str, Any]]:
        return list(self._prompts.values())

    def get_prompt(self, name: str, version: str) -> Optional[Dict[str, Any]]:
        key = f"{name}:{version}"
        if key in self._prompts:
            return self._prompts[key]
        for p in self._prompts.values():
            if p["version"] == version:
                return p
        template = get_prompt_template(version)
        return {
            "name": name,
            "version": version,
            "filename": f"{name}_{version}.txt",
            "type": "scoring",
            "template": template,
        }

    def register_prompt(
        self,
        name: str,
        version: str,
        template: str,
        prompt_type: str = "scoring",
    ) -> Dict[str, Any]:
        item = {
            "name": name,
            "version": version,
            "filename": f"{name}_{version}.txt",
            "type": prompt_type,
            "template": template,
        }
        self._prompts[f"{name}:{version}"] = item
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
