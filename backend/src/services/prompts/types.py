from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RegisterPromptCommand(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    version: str
    template: str
    prompt_type: str = "scoring"
    description: Optional[str] = None


class PromptRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    version: str
    template: str
    prompt_type: str = "scoring"
    description: Optional[str] = None


class PromptItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    version: str
    filename: Optional[str] = None
    type: str = "scoring"
    template: str
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class PromptListResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    prompts: List[PromptItem] = Field(default_factory=list)
    total: int = 0


class PromptDeleteResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    success: bool = True
    message: str
