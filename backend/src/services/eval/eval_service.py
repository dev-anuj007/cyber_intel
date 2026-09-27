import concurrent.futures
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.core.config import ROOT_DIR
from src.services.eval.dependencies import (
    EvalServiceDependencyContext,
    get_eval_dependency_context,
)
from src.services.eval.eval_harness import (
    generate_comparison_dict,
)
from src.services.eval.eval_harness import (
    run_eval as harness_run_eval,
)
from src.services.eval.protocols import IEvalReader, IEvalService, IEvalWriter
from src.services.eval.types import (
    ComparePromptsCommand,
    RunEvalCommand,
)
from src.services.logger.logger_service import get_logger

logger = get_logger("services.eval")


class EvalService(IEvalService):
    def __init__(
        self,
        context: Optional[EvalServiceDependencyContext] = None,
    ):
        ctx = context or get_eval_dependency_context()
        self._reader: IEvalReader = ctx.reader
        self._writer: IEvalWriter = ctx.writer
        self.reader = self._reader
        self.writer = self._writer
        self._prompt_service = ctx.prompt_service

        self.root_dir = ROOT_DIR
        self.db_path = ctx.db_path
        self.evals_dir = ctx.evals_dir or Path(__file__).resolve().parent

        if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
            self.results_dir = Path("/tmp/evals/results")
        else:
            self.results_dir = self.evals_dir / "results"

        try:
            self.results_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError):
            self.results_dir = Path("/tmp/evals/results")
            self.results_dir.mkdir(parents=True, exist_ok=True)

    def _get_prompt_service(self) -> Any:
        if self._prompt_service is not None:
            return self._prompt_service
        from src.services.prompts.dependencies import default_prompt_service

        return default_prompt_service

    def _resolve_eval_set_path(self, override: Optional[str] = None) -> str:
        if override and Path(override).exists():
            return override
        candidates = [
            self.evals_dir / "labeled_sets" / "eval_v1.json",
            Path(__file__).resolve().parent / "labeled_sets" / "eval_v1.json",
            Path("/var/task/src/services/eval/labeled_sets/eval_v1.json"),
            Path("/tmp/evals/labeled_sets/eval_v1.json"),
        ]
        for c in candidates:
            if c.exists():
                return str(c)
        return str(self.evals_dir / "labeled_sets" / "eval_v1.json")

    def list_prompts(self) -> List[Dict[str, Any]]:
        return self._get_prompt_service().list_prompts()

    def get_default_dataset(self) -> List[Dict[str, Any]]:
        target_path = self._resolve_eval_set_path()
        if Path(target_path).exists():
            with open(target_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

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
    ) -> Dict[str, Any]:
        if isinstance(prompt_version, RunEvalCommand):
            target_version = prompt_version.prompt_version
            target_custom_template = prompt_version.custom_prompt_template
            target_dry_run = prompt_version.dry_run
            target_api_key = prompt_version.api_key
            target_eval_set_path = prompt_version.eval_set_path
            target_eval_set = prompt_version.eval_set
            target_sample_limit = prompt_version.sample_limit
            target_progress_cb = prompt_version.progress_callback
        else:
            target_version = prompt_version
            target_custom_template = custom_prompt_template
            target_dry_run = dry_run
            target_api_key = api_key
            target_eval_set_path = eval_set_path
            target_eval_set = eval_set
            target_sample_limit = sample_limit
            target_progress_cb = progress_callback

        with logger.span("eval.run", prompt_version=target_version, dry_run=target_dry_run):
            resolved_set_path = self._resolve_eval_set_path(target_eval_set_path) if not target_eval_set else None

            results = harness_run_eval(
                eval_set_path=resolved_set_path,
                eval_set_data=target_eval_set,
                prompt_version=target_version,
                skip_scoring=target_dry_run,
                api_key=target_api_key,
                custom_prompt_template=target_custom_template,
                sample_limit=target_sample_limit,
                progress_callback=target_progress_cb,
            )

            saved_path = self._writer.save_results(
                results,
                version=target_version,
                out_dir=str(self.results_dir),
            )

            saved_file_name = saved_path.name if hasattr(saved_path, "name") else str(saved_path)
            logger.info("Evaluation run completed", prompt_version=target_version, saved_file=saved_file_name)

            return {
                "success": True,
                "prompt_version": target_version,
                "results": results,
                "saved_file": saved_file_name,
                "timestamp": datetime.now().isoformat(),
            }

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
    ) -> Dict[str, Any]:
        if isinstance(prompt_a, ComparePromptsCommand):
            target_prompt_a = prompt_a.prompt_a
            target_prompt_b = prompt_a.prompt_b
            target_custom_a = prompt_a.custom_prompt_a
            target_custom_b = prompt_a.custom_prompt_b
            target_dry_run = prompt_a.dry_run
            target_file_a = prompt_a.file_a
            target_file_b = prompt_a.file_b
            target_api_key = prompt_a.api_key
            target_eval_set_path = prompt_a.eval_set_path
            target_eval_set = prompt_a.eval_set
            target_sample_limit = prompt_a.sample_limit
            target_progress_cb = prompt_a.progress_callback
        else:
            target_prompt_a = prompt_a
            target_prompt_b = prompt_b
            target_custom_a = custom_prompt_a
            target_custom_b = custom_prompt_b
            target_dry_run = dry_run
            target_file_a = file_a
            target_file_b = file_b
            target_api_key = api_key
            target_eval_set_path = eval_set_path
            target_eval_set = eval_set
            target_sample_limit = sample_limit
            target_progress_cb = progress_callback

        with logger.span("eval.compare", prompt_a=target_prompt_a, prompt_b=target_prompt_b, dry_run=target_dry_run):
            resolved_set_path = self._resolve_eval_set_path(target_eval_set_path) if not target_eval_set else None

            if target_file_a and target_file_b:
                data_a = self._reader.read_result_file(self.results_dir, target_file_a) or {}
                data_b = self._reader.read_result_file(self.results_dir, target_file_b) or {}
                res_a = data_a.get("results", {})
                res_b = data_b.get("results", {})
            else:
                completed_lock = threading.Lock()
                completed_total = 0

                def make_cb(label: str):
                    last_reported = 0

                    def cb(curr: int, tot: int, meta: Optional[Dict[str, Any]] = None, partial: Optional[Any] = None):
                        nonlocal last_reported
                        if target_progress_cb:
                            with completed_lock:
                                nonlocal completed_total
                                delta = curr - last_reported
                                last_reported = curr
                                completed_total += delta
                                total_expected = 2 * tot if tot > 0 else 2
                                try:
                                    target_progress_cb(
                                        completed_total,
                                        total_expected,
                                        {
                                            "stage": f"Evaluating {label}",
                                            "prompt_a": target_prompt_a,
                                            "prompt_b": target_prompt_b,
                                            "completed_total": completed_total,
                                            "total_expected": total_expected,
                                        },
                                        None,
                                    )
                                except Exception as cb_exc:
                                    logger.debug(f"Compare progress callback error: {cb_exc}")

                    return cb

                def run_a():
                    return harness_run_eval(
                        eval_set_path=resolved_set_path,
                        eval_set_data=target_eval_set,
                        prompt_version=target_prompt_a,
                        skip_scoring=target_dry_run,
                        api_key=target_api_key,
                        custom_prompt_template=target_custom_a,
                        sample_limit=target_sample_limit,
                        progress_callback=make_cb(target_prompt_a),
                    )

                def run_b():
                    return harness_run_eval(
                        eval_set_path=resolved_set_path,
                        eval_set_data=target_eval_set,
                        prompt_version=target_prompt_b,
                        skip_scoring=target_dry_run,
                        api_key=target_api_key,
                        custom_prompt_template=target_custom_b,
                        sample_limit=target_sample_limit,
                        progress_callback=make_cb(target_prompt_b),
                    )

                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                    fut_a = pool.submit(run_a)
                    fut_b = pool.submit(run_b)
                    res_a = fut_a.result()
                    res_b = fut_b.result()

                self._writer.save_results(res_a, version=target_prompt_a, out_dir=str(self.results_dir))
                self._writer.save_results(res_b, version=target_prompt_b, out_dir=str(self.results_dir))

            comparison = generate_comparison_dict(res_a, res_b)
            logger.info("Evaluation comparison completed", prompt_a=target_prompt_a, prompt_b=target_prompt_b)

            return {
                "success": True,
                "comparison": comparison,
                "results_a": res_a,
                "results_b": res_b,
                "timestamp": datetime.now().isoformat(),
            }

    def handle_eval_job(
        self,
        job_id: str,
        payload: Dict[str, Any],
        progress_callback: Optional[Any] = None,
    ) -> Dict[str, Any]:
        prompt_version = payload.get("prompt_version", "v2.0")
        custom_prompt_template = payload.get("custom_prompt_template")
        dry_run = payload.get("dry_run", True)
        api_key = payload.get("api_key")
        eval_set_path = payload.get("eval_set_path")
        eval_set = payload.get("eval_set")
        sample_limit = payload.get("sample_limit")

        eval_output = self.run_eval(
            prompt_version=prompt_version,
            custom_prompt_template=custom_prompt_template,
            dry_run=dry_run,
            api_key=api_key,
            eval_set_path=eval_set_path,
            eval_set=eval_set,
            sample_limit=sample_limit,
            progress_callback=progress_callback,
        )

        return {
            "results": eval_output,
            "metadata": {
                "prompt_version": prompt_version,
                "dry_run": dry_run,
                "total_samples": eval_output.get("results", {}).get("total", 0),
                "tier_accuracy": eval_output.get("results", {}).get("tier_accuracy", 0.0),
                "saved_file": eval_output.get("saved_file"),
            },
        }

    def handle_eval_compare_job(
        self,
        job_id: str,
        payload: Dict[str, Any],
        progress_callback: Optional[Any] = None,
    ) -> Dict[str, Any]:
        prompt_a = payload.get("prompt_a", "v1.0")
        prompt_b = payload.get("prompt_b", "v2.0")
        custom_prompt_a = payload.get("custom_prompt_a")
        custom_prompt_b = payload.get("custom_prompt_b")
        dry_run = payload.get("dry_run", True)
        file_a = payload.get("file_a")
        file_b = payload.get("file_b")
        api_key = payload.get("api_key")
        eval_set_path = payload.get("eval_set_path")
        eval_set = payload.get("eval_set")
        sample_limit = payload.get("sample_limit")

        compare_output = self.compare_prompts(
            prompt_a=prompt_a,
            prompt_b=prompt_b,
            custom_prompt_a=custom_prompt_a,
            custom_prompt_b=custom_prompt_b,
            dry_run=dry_run,
            file_a=file_a,
            file_b=file_b,
            api_key=api_key,
            eval_set_path=eval_set_path,
            eval_set=eval_set,
            sample_limit=sample_limit,
            progress_callback=progress_callback,
        )

        return {
            "results": compare_output,
            "metadata": {
                "prompt_a": prompt_a,
                "prompt_b": prompt_b,
                "dry_run": dry_run,
            },
        }

    def list_history(self) -> List[Dict[str, Any]]:
        return self._reader.list_history(self.results_dir)

    def get_result_file(self, filename: str) -> Optional[Dict[str, Any]]:
        return self._reader.read_result_file(self.results_dir, filename)


default_eval_service = EvalService()
