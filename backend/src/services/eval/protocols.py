from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from src.services.eval.types import (
    ComparePromptsCommand,
    EvalCompareResult,
    EvalHistoryItem,
    EvalRunResult,
    RunEvalCommand,
)


@runtime_checkable
class IEvalReader(Protocol):
    def list_prompts(
        self, prompts_dir: Optional[Path] = None
    ) -> List[Dict[str, Any]]: ...

    def list_history(self, results_dir: Path) -> List[EvalHistoryItem]: ...

    def get_history_file(
        self, results_dir: Path, filename: str
    ) -> Optional[Dict[str, Any]]: ...

    def read_result_file(
        self, results_dir: Path, filename: str
    ) -> Optional[Dict[str, Any]]: ...

    def get_run_by_id(self, conn: Any, run_id: str) -> Optional[Dict[str, Any]]: ...

    def get_runs(
        self, conn: Any, prompt_version: Optional[str] = None, limit: int = 20
    ) -> List[Dict[str, Any]]: ...


@runtime_checkable
class IEvalWriter(Protocol):
    def save_run(self, conn: Any, run_record: dict) -> str: ...

    def save_results(
        self,
        results: dict,
        version: str = "v1.0",
        out_dir: str = "results",
        conn: Optional[Any] = None,
    ) -> Path: ...


@runtime_checkable
class IEvalService(Protocol):
    def list_prompts(self) -> List[Any]: ...

    def get_default_dataset(self) -> List[Dict[str, Any]]: ...

    def run_eval(self, command: RunEvalCommand) -> EvalRunResult: ...

    def compare_prompts(self, command: ComparePromptsCommand) -> EvalCompareResult: ...

    def list_history(self) -> List[EvalHistoryItem]: ...

    def get_result_file(self, filename: str) -> Optional[Dict[str, Any]]: ...

    def handle_eval_job(
        self,
        job_id: str,
        payload: Dict[str, Any],
        progress_callback: Optional[Any] = None,
    ) -> Dict[str, Any]: ...

    def handle_eval_compare_job(
        self,
        job_id: str,
        payload: Dict[str, Any],
        progress_callback: Optional[Any] = None,
    ) -> Dict[str, Any]: ...
