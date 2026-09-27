from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Union, runtime_checkable

from src.services.eval.types import ComparePromptsCommand, RunEvalCommand


@runtime_checkable
class IEvalReader(Protocol):
    def list_prompts(self, prompts_dir: Optional[Path] = None) -> List[Dict[str, Any]]: ...

    def list_history(self, results_dir: Path) -> List[Dict[str, Any]]: ...

    def get_history_file(self, results_dir: Path, filename: str) -> Optional[Dict[str, Any]]: ...

    def read_result_file(self, results_dir: Path, filename: str) -> Optional[Dict[str, Any]]: ...

    def get_run_by_id(self, conn: Any, run_id: str) -> Optional[Dict[str, Any]]: ...

    def get_runs(self, conn: Any, prompt_version: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]: ...


@runtime_checkable
class IEvalWriter(Protocol):
    def save_run(self, conn: Any, run_record: dict) -> str: ...

    def save_results(self, results: dict, version: str = "v1.0", out_dir: str = "results") -> Path: ...


@runtime_checkable
class IEvalService(Protocol):
    def list_prompts(self) -> List[Dict[str, Any]]: ...

    def get_default_dataset(self) -> List[Dict[str, Any]]: ...

    def run_eval(
        self,
        prompt_version: Union[str, RunEvalCommand] = "v2.0",
        custom_prompt_template: Optional[str] = None,
        dry_run: bool = True,
        api_key: Optional[str] = None,
        eval_set_path: Optional[str] = None,
        eval_set: Optional[List[Dict[str, Any]]] = None,
        sample_limit: Optional[int] = None,
        progress_callback: Optional[Any] = None,
    ) -> Dict[str, Any]: ...

    def compare_prompts(
        self,
        prompt_a: Union[str, ComparePromptsCommand] = "v1.0",
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
        progress_callback: Optional[Any] = None,
    ) -> Dict[str, Any]: ...

    def list_history(self) -> List[Dict[str, Any]]: ...

    def get_result_file(self, filename: str) -> Optional[Dict[str, Any]]: ...



