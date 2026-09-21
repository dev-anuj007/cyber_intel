from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from pydantic import BaseModel

from src.services.accounts.types import Account
from src.services.scorer.types import PriorityTier


class EvalExample(BaseModel):
    account_key: str
    account: Account
    expected_tier: PriorityTier
    expected_score: int
    reasoning: str


class EvalRunRequest(BaseModel):
    prompt_version: str = "v2.0"
    custom_prompt_template: Optional[str] = None
    dry_run: bool = True
    eval_set_path: Optional[str] = None
    eval_set: Optional[List[Dict[str, Any]]] = None
    sample_limit: Optional[int] = None


class EvalCompareRequest(BaseModel):
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


class IEvalReader(Protocol):
    def list_prompts(self, prompts_dir: Path) -> List[Dict[str, Any]]: ...

    def list_history(self, results_dir: Path) -> List[Dict[str, Any]]: ...

    def get_history_file(self, results_dir: Path, filename: str) -> Optional[Dict[str, Any]]: ...

    def read_result_file(self, results_dir: Path, filename: str) -> Optional[Dict[str, Any]]: ...


class IEvalWriter(Protocol):
    def save_results(self, results: dict, version: str, out_dir: str) -> Path: ...


class IEvalService(Protocol):
    def list_prompts(self) -> List[Dict[str, Any]]: ...

    def get_default_dataset(self) -> List[Dict[str, Any]]: ...

    def run_eval(
        self,
        prompt_version: str = "v2.0",
        custom_prompt_template: Optional[str] = None,
        dry_run: bool = True,
        api_key: Optional[str] = None,
        eval_set_path: Optional[str] = None,
        eval_set: Optional[List[Dict[str, Any]]] = None,
        sample_limit: Optional[int] = None,
    ) -> Dict[str, Any]: ...

    def compare_prompts(
        self,
        prompt_a: str = "v1.0",
        prompt_b: str = "v2.0",
        custom_prompt_a: Optional[str] = None,
        custom_prompt_b: Optional[str] = None,
        dry_run: bool = True,
        file_a: Optional[str] = None,
        file_b: Optional[str] = None,
        api_key: Optional[str] = None,
        eval_set_path: Optional[str] = None,
        eval_set: Optional[List[Dict[str, Any]]] = None,
        sample_limit: Optional[int] = None,
    ) -> Dict[str, Any]: ...

    def list_history(self) -> List[Dict[str, Any]]: ...

    def get_result_file(self, filename: str) -> Optional[Dict[str, Any]]: ...
