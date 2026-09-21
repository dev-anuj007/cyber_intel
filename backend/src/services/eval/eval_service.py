import concurrent.futures
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.config import ROOT_DIR
from src.services.database import is_deployed
from src.services.eval.eval_harness import (
    generate_comparison_dict,
)
from src.services.eval.eval_harness import (
    run_eval as harness_run_eval,
)
from src.services.eval.eval_types import IEvalReader, IEvalService, IEvalWriter
from src.services.eval.repositories.reader import EvalReader
from src.services.eval.repositories.writer import EvalWriter
from src.services.jobs.jobs_service import default_jobs_service
from src.services.logger import get_logger
from src.services.prompts.prompt_service import PromptService, default_prompt_service

logger = get_logger("services.eval")


class EvalService(IEvalService):
    def __init__(
        self,
        evals_dir: Optional[Path] = None,
        reader: Optional[IEvalReader] = None,
        writer: Optional[IEvalWriter] = None,
        prompt_service: Optional[PromptService] = None,
        db_path: Optional[Any] = None,
        **kwargs,
    ):
        self.root_dir = ROOT_DIR
        self.db_path = db_path
        self.evals_dir = evals_dir or Path(__file__).resolve().parent
        self.prompt_service = prompt_service or default_prompt_service

        self.reader = reader or EvalReader()
        self.writer = writer or EvalWriter()

        if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
            self.results_dir = Path("/tmp/evals/results")
        else:
            self.results_dir = self.evals_dir / "results"

        try:
            self.results_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError):
            self.results_dir = Path("/tmp/evals/results")
            self.results_dir.mkdir(parents=True, exist_ok=True)

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
        return self.prompt_service.list_prompts()

    def get_default_dataset(self) -> List[Dict[str, Any]]:
        target_path = self._resolve_eval_set_path()
        if Path(target_path).exists():
            with open(target_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def run_eval(
        self,
        prompt_version: str = "v2.0",
        custom_prompt_template: Optional[str] = None,
        dry_run: bool = True,
        api_key: Optional[str] = None,
        eval_set_path: Optional[str] = None,
        eval_set: Optional[List[Dict[str, Any]]] = None,
        sample_limit: Optional[int] = None,
        progress_callback: Optional[Any] = None,
    ) -> Dict[str, Any]:
        with logger.span("eval.run", prompt_version=prompt_version, dry_run=dry_run):
            target_set_path = self._resolve_eval_set_path(eval_set_path) if not eval_set else None

            results = harness_run_eval(
                eval_set_path=target_set_path,
                eval_set_data=eval_set,
                prompt_version=prompt_version,
                skip_scoring=dry_run,
                api_key=api_key,
                custom_prompt_template=custom_prompt_template,
                sample_limit=sample_limit,
                progress_callback=progress_callback,
            )

            saved_path = self.writer.save_results(
                results,
                version=prompt_version,
                out_dir=str(self.results_dir),
            )

            saved_file_name = saved_path.name if hasattr(saved_path, "name") else str(saved_path)
            logger.info("Evaluation run completed", prompt_version=prompt_version, saved_file=saved_file_name)

            return {
                "success": True,
                "prompt_version": prompt_version,
                "results": results,
                "saved_file": saved_file_name,
                "timestamp": datetime.now().isoformat(),
            }

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
        progress_callback: Optional[Any] = None,
    ) -> Dict[str, Any]:
        with logger.span("eval.compare", prompt_a=prompt_a, prompt_b=prompt_b, dry_run=dry_run):
            target_set_path = self._resolve_eval_set_path(eval_set_path) if not eval_set else None

            if file_a and file_b:
                data_a = self.reader.read_result_file(self.results_dir, file_a) or {}
                data_b = self.reader.read_result_file(self.results_dir, file_b) or {}
                res_a = data_a.get("results", {})
                res_b = data_b.get("results", {})
            else:
                completed_lock = threading.Lock()
                completed_total = 0

                def make_cb(label: str):
                    last_reported = 0

                    def cb(curr: int, tot: int, meta: Optional[Dict[str, Any]] = None, partial: Optional[Any] = None):
                        nonlocal last_reported
                        if progress_callback:
                            with completed_lock:
                                nonlocal completed_total
                                delta = curr - last_reported
                                last_reported = curr
                                completed_total += delta
                                total_expected = 2 * tot if tot > 0 else 2
                                try:
                                    progress_callback(
                                        completed_total,
                                        total_expected,
                                        {
                                            "stage": f"Evaluating {label}",
                                            "prompt_a": prompt_a,
                                            "prompt_b": prompt_b,
                                            "completed_total": completed_total,
                                            "total_expected": total_expected,
                                        },
                                        None,
                                    )
                                except Exception as cb_exc:
                                    logger.debug(f"Compare progress callback error: {cb_exc}")

                    return cb

                # Run prompt A and prompt B evaluations in parallel
                def run_a():
                    return harness_run_eval(
                        eval_set_path=target_set_path,
                        eval_set_data=eval_set,
                        prompt_version=prompt_a,
                        skip_scoring=dry_run,
                        api_key=api_key,
                        custom_prompt_template=custom_prompt_a,
                        sample_limit=sample_limit,
                        progress_callback=make_cb(prompt_a),
                    )

                def run_b():
                    return harness_run_eval(
                        eval_set_path=target_set_path,
                        eval_set_data=eval_set,
                        prompt_version=prompt_b,
                        skip_scoring=dry_run,
                        api_key=api_key,
                        custom_prompt_template=custom_prompt_b,
                        sample_limit=sample_limit,
                        progress_callback=make_cb(prompt_b),
                    )

                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                    fut_a = pool.submit(run_a)
                    fut_b = pool.submit(run_b)
                    res_a = fut_a.result()
                    res_b = fut_b.result()

                self.writer.save_results(res_a, version=prompt_a, out_dir=str(self.results_dir))
                self.writer.save_results(res_b, version=prompt_b, out_dir=str(self.results_dir))

            comparison = generate_comparison_dict(res_a, res_b)
            logger.info("Evaluation comparison completed", prompt_a=prompt_a, prompt_b=prompt_b)

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
        return self.reader.list_history(self.results_dir)

    def get_result_file(self, filename: str) -> Optional[Dict[str, Any]]:
        return self.reader.read_result_file(self.results_dir, filename)


default_eval_service = EvalService()

default_jobs_service.register_handler("eval_run", default_eval_service.handle_eval_job)
default_jobs_service.register_handler("eval_compare", default_eval_service.handle_eval_compare_job)
