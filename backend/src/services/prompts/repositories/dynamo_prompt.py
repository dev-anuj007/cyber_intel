from datetime import datetime
from typing import List, Dict, Any, Optional

from src.services.database import (
    get_dynamo_resource,
    get_table_name,
    decimal_to_python,
)
from src.services.prompts.templates import CANONICAL_PROMPTS_LIST, get_prompt_template
from src.services.prompts.prompt_types import IPromptRepository
from src.services.logger import get_logger

logger = get_logger("services.prompts.dynamo")


class DynamoPromptRepository(IPromptRepository):
    def __init__(self, table_name: Optional[str] = None):
        self._table_name = table_name or get_table_name("prompts")

    def _get_table(self):
        return get_dynamo_resource().Table(self._table_name)

    def list_prompts(self) -> List[Dict[str, Any]]:
        with logger.span("prompts.dynamo.list"):
            table = self._get_table()
            try:
                response = table.scan()
                items = response.get("Items", [])
                if items:
                    py_items = [decimal_to_python(item) for item in items]
                    py_items.sort(key=lambda x: (x.get("name", ""), x.get("version", "")), reverse=True)
                    return py_items
            except Exception as e:
                logger.warning(f"Error scanning DynamoDB prompts table: {e}")

            self.seed_defaults()
            try:
                response = table.scan()
                items = response.get("Items", [])
                if items:
                    return [decimal_to_python(item) for item in items]
            except Exception:
                pass

            return CANONICAL_PROMPTS_LIST

    def get_prompt(self, name: str, version: str) -> Optional[Dict[str, Any]]:
        table = self._get_table()
        try:
            response = table.get_item(Key={"name": name, "version": version})
            item = response.get("Item")
            if item:
                return decimal_to_python(item)
        except Exception as e:
            logger.warning(f"Error fetching prompt {name}:{version}: {e}")

        for p in CANONICAL_PROMPTS_LIST:
            if p["name"] == name and p["version"] == version:
                return p
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
            "updated_at": datetime.now().isoformat(),
        }
        table = self._get_table()
        table.put_item(Item=item)
        logger.info("Registered prompt template to DynamoDB", name=name, version=version)
        return item

    def seed_defaults(self):
        table = self._get_table()
        for seed in CANONICAL_PROMPTS_LIST:
            item = {
                "name": seed["name"],
                "version": seed["version"],
                "filename": seed["filename"],
                "type": seed["type"],
                "template": seed["template"],
                "created_at": datetime.now().isoformat(),
            }
            try:
                table.put_item(Item=item)
            except Exception as e:
                logger.warning(f"Failed to pre-seed prompt {seed['filename']}: {e}")
