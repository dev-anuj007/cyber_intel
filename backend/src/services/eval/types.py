from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, ConfigDict

from src.services.accounts.types import Account
from src.services.scorer.types import PriorityTier


class EvalExample(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    account_key: str
    account: Account
    expected_tier: PriorityTier
    expected_score: int
    reasoning: str


class EvalRunRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    prompt_version: str = "v2.0"
    custom_prompt_template: Optional[str] = None
    dry_run: bool = True
    eval_set_path: Optional[str] = None
    eval_set: Optional[List[Dict[str, Any]]] = None
    sample_limit: Optional[int] = None


class EvalCompareRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    prompt_a: str = "v1.0"
    prompt_b: str = "v2.0"
    custom_prompt_a: Optional[str] = None
    custom_prompt_b: Optional[str] = None
    dry_run: bool = True
    file_a: Optional[str] = None
    file_b: Optional[str] = None
    eval_set_path: Optional[str] = None
    eval_set: Optional[List[Dict[str, Any]]] = None
    sample_limit: Optional[int] = None


class RunEvalCommand(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    prompt_version: str = "v2.0"
    custom_prompt_template: Optional[str] = None
    dry_run: bool = True
    api_key: Optional[str] = None
    eval_set_path: Optional[str] = None
    eval_set: Optional[List[Dict[str, Any]]] = None
    sample_limit: Optional[int] = None
    progress_callback: Optional[Any] = None


class ComparePromptsCommand(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    prompt_a: str = "v1.0"
    prompt_b: str = "v2.0"
    custom_prompt_a: Optional[str] = None
    custom_prompt_b: Optional[str] = None
    dry_run: bool = True
    file_a: Optional[str] = None
    file_b: Optional[str] = None
    api_key: Optional[str] = None
    eval_set_path: Optional[str] = None
    eval_set: Optional[List[Dict[str, Any]]] = None
    sample_limit: Optional[int] = None
    progress_callback: Optional[Any] = None



