from typing import Optional
from fastapi import APIRouter, Depends

from src.core.exceptions import (
    AuthenticationError,
    InvalidInputError,
    NotFoundError,
)
from src.services.prompts.prompt_types import PromptRegisterRequest
from src.services.prompts.prompt_service import PromptService, default_prompt_service
from src.services.auth.api import get_current_user_optional
from src.services.logger import get_logger

logger = get_logger("prompts.api")

router = APIRouter(prefix="/api/prompts", tags=["Prompt Registry & Management"])


def get_prompt_service() -> PromptService:
    return default_prompt_service


@router.get("")
@router.get("/")
def list_prompts(prompt_service: PromptService = Depends(get_prompt_service)):
    prompts = prompt_service.list_prompts()
    return {"prompts": prompts}


@router.get("/{name}/{version}")
def get_prompt(
    name: str,
    version: str,
    prompt_service: PromptService = Depends(get_prompt_service),
):
    prompt = prompt_service.get_prompt(name=name, version=version)
    if not prompt:
        raise NotFoundError(message=f"Prompt '{name}:{version}' not found", code="PROMPT_NOT_FOUND")
    return prompt


@router.post("")
@router.post("/")
def register_prompt(
    req: PromptRegisterRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    prompt_service: PromptService = Depends(get_prompt_service),
):
    if not req.name or not req.version or not req.template:
        raise InvalidInputError(message="Name, version, and template are required", code="INVALID_PROMPT_INPUT")

    return prompt_service.register_prompt(
        name=req.name,
        version=req.version,
        template=req.template,
        prompt_type=req.prompt_type,
    )
