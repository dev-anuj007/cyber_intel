from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class PromptRegisterRequest(BaseModel):
    name: str
    version: str
    template: str
    prompt_type: str = "scoring"


class RegisterPromptCommand(BaseModel):
    name: str
    version: str
    template: str
    prompt_type: str = "scoring"


class PromptItem(BaseModel):
    name: str
    version: str
    filename: Optional[str] = None
    type: str = "scoring"
    template: str
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class PromptListResponse(BaseModel):
    items: List[Dict[str, Any]]
    total: int
