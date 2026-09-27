from typing import Optional

from fastapi import APIRouter, Depends

from src.core.exceptions import InvalidInputError, NotFoundError
from src.services.auth.dependencies import get_current_user_optional
from src.services.logger.logger_service import get_logger
from src.services.prompts.dependencies import get_prompt_service
from src.services.prompts.protocols import IPromptService
from src.services.prompts.types import (
    PromptDeleteResponse,
    PromptItem,
    PromptListResponse,
    PromptRegisterRequest,
)

logger = get_logger("prompts.api")

router = APIRouter(prefix="/api/prompts", tags=["Prompt Registry & Management"])


@router.get("", response_model=PromptListResponse)
@router.get("/", response_model=PromptListResponse)
def list_prompts(
    prompt_service: IPromptService = Depends(get_prompt_service),
) -> PromptListResponse:
    prompts = prompt_service.list_prompts()
    return PromptListResponse(prompts=prompts, total=len(prompts))


@router.get("/{name}/{version}", response_model=PromptItem)
def get_prompt(
    name: str,
    version: str,
    prompt_service: IPromptService = Depends(get_prompt_service),
) -> PromptItem:
    prompt = prompt_service.get_prompt(name=name, version=version)
    if not prompt:
        raise NotFoundError(
            message=f"Prompt '{name}:{version}' not found",
            code="PROMPT_NOT_FOUND",
        )
    return prompt


@router.post("", response_model=PromptItem)
@router.post("/", response_model=PromptItem)
def register_prompt(
    req: PromptRegisterRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    prompt_service: IPromptService = Depends(get_prompt_service),
) -> PromptItem:
    if not req.name or not req.version or not req.template:
        raise InvalidInputError(
            message="Name, version, and template are required",
            code="INVALID_PROMPT_INPUT",
        )

    return prompt_service.register_prompt(
        name=req.name,
        version=req.version,
        template=req.template,
        prompt_type=req.prompt_type,
        description=req.description,
    )


@router.delete("/{name}/{version}", response_model=PromptDeleteResponse)
def delete_prompt(
    name: str,
    version: str,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    prompt_service: IPromptService = Depends(get_prompt_service),
) -> PromptDeleteResponse:
    if version in ["v1.0", "v2.0"] and (name == "account_scoring" or not name):
        raise InvalidInputError(
            message="Cannot delete built-in canonical prompt versions (v1.0, v2.0)",
            code="CANNOT_DELETE_CANONICAL_PROMPT",
        )

    success = prompt_service.delete_prompt(name=name, version=version)
    if not success:
        raise NotFoundError(
            message=f"Prompt '{name}:{version}' not found",
            code="PROMPT_NOT_FOUND",
        )
    return PromptDeleteResponse(
        success=True,
        message=f"Prompt '{name}:{version}' deleted successfully",
    )
