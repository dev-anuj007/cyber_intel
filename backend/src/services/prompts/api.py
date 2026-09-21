from typing import Optional

from fastapi import APIRouter, Depends

from src.core.exceptions import (
    InvalidInputError,
    NotFoundError,
)
from src.services.auth.api import get_current_user_optional
from src.services.logger import get_logger
from src.services.prompts.prompt_service import PromptService, default_prompt_service
from src.services.prompts.prompt_types import PromptRegisterRequest

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


@router.delete("/{name}/{version}")
def delete_prompt(
    name: str,
    version: str,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    prompt_service: PromptService = Depends(get_prompt_service),
):
    # Guard against deleting core canonical prompts
    if version in ["v1.0", "v2.0"] and (name == "account_scoring" or not name):
        raise InvalidInputError(
            message="Cannot delete built-in canonical prompt versions (v1.0, v2.0)",
            code="CANNOT_DELETE_CANONICAL_PROMPT",
        )

    success = prompt_service.delete_prompt(name=name, version=version)
    if not success:
        raise NotFoundError(message=f"Prompt '{name}:{version}' not found", code="PROMPT_NOT_FOUND")
    return {"success": True, "message": f"Prompt '{name}:{version}' deleted successfully"}
