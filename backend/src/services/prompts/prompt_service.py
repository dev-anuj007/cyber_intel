from typing import Optional, List, Dict, Any

from src.services.prompts.prompt_types import IPromptService, IPromptRepository
from src.services.prompts.repositories.reader import LocalPromptRepository
from src.services.prompts.repositories.dynamo_prompt import DynamoPromptRepository
from src.services.prompts.templates import CANONICAL_PROMPTS_LIST, get_prompt_template
from src.services.database import is_deployed
from src.services.logger import get_logger

logger = get_logger("services.prompts")


class PromptService(IPromptService):
    def __init__(self, repository: Optional[IPromptRepository] = None):
        if is_deployed():
            self.repository = repository or DynamoPromptRepository()
        else:
            self.repository = repository or LocalPromptRepository()

    def list_prompts(self) -> List[Dict[str, Any]]:
        with logger.span("prompts.list"):
            return self.repository.list_prompts()

    def get_prompt(self, name: str, version: str) -> Optional[Dict[str, Any]]:
        with logger.span("prompts.get", prompt_name=name, version=version):
            return self.repository.get_prompt(name=name, version=version)

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
        with logger.span("prompts.register", prompt_name=name, version=version):
            return self.repository.register_prompt(
                name=name,
                version=version,
                template=template,
                prompt_type=prompt_type,
            )


default_prompt_service = PromptService()
