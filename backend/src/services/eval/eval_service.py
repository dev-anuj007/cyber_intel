import concurrent.futures
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.config import ROOT_DIR
from src.services.eval.dependencies import (
    EvalServiceDependencyContext,
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
    EvalCompareResult,
    EvalHistoryItem,
    EvalMetricDetails,
    EvalRunResult,
    PromptComparisonMetrics,
    RunEvalCommand,
)


class EvalService(IEvalService):
    def __init__(
        self,
        context: EvalServiceDependencyContext,
    ) -> None:
        self.context: EvalServiceDependencyContext = context
        self._reader: IEvalReader = self.context.reader
        self._writer: IEvalWriter = self.context.writer
        self.reader: IEvalReader = self._reader
        self.writer: IEvalWriter = self._writer
        self._prompt_service = self.context.prompt_service

        self.root_dir = ROOT_DIR
        self.db_path = self.context.db_path
        self.evals_dir = self.context.evals_dir or Path(__file__).resolve().parent

        if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
            self.results_dir = Path("/tmp/evals/results")
        else:
            self.results_dir = self.evals_dir / "results"

        try:
            self.results_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError):
            self.results_dir = Path("/tmp/evals/results")
            self.results_dir.mkdir(parents=True, exist_ok=True)

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
        command: RunEvalCommand,
    ) -> EvalRunResult:
        target_version = command.prompt_version
        target_custom_template = command.custom_prompt_template
        target_dry_run = command.dry_run
        target_api_key = command.api_key
        target_eval_set_path = command.eval_set_path
        target_eval_set = command.eval_set
        target_sample_limit = command.sample_limit
        target_progress_cb = command.progress_callback

        with self.context.logger.span(
            "eval.run", prompt_version=target_version, dry_run=target_dry_run
        ):
            resolved_set_path = (
                self._resolve_eval_set_path(target_eval_set_path)
                if not target_eval_set
                else None
            )

            raw_results = harness_run_eval(
                eval_set_path=resolved_set_path,
                eval_set_data=target_eval_set,
                prompt_version=target_version,
                skip_scoring=target_dry_run,
                api_key=target_api_key,
                custom_prompt_template=target_custom_template,
                sample_limit=target_sample_limit,
                progress_callback=target_progress_cb,
            )

            with self.context.db_service.get_connection() as conn:
                saved_path = self._writer.save_results(
                    raw_results,
                    version=target_version,
                    out_dir=str(self.results_dir),
                    conn=conn,
                )

            saved_file_name = (
                saved_path.name if hasattr(saved_path, "name") else str(saved_path)
            )
            self.context.logger.info(
                "Evaluation run completed",
                prompt_version=target_version,
                saved_file=saved_file_name,
            )

            metrics_dto = EvalMetricDetails(**raw_results)
            return EvalRunResult(
                success=True,
                prompt_version=target_version,
                results=metrics_dto,
                saved_file=saved_file_name,
                timestamp=datetime.now().isoformat(),
            )

    def compare_prompts(
        self,
        command: ComparePromptsCommand,
    ) -> EvalCompareResult:
        target_prompt_a = command.prompt_a
        target_prompt_b = command.prompt_b
        target_custom_a = command.custom_prompt_a
        target_custom_b = command.custom_prompt_b
        target_dry_run = command.dry_run
        target_file_a = command.file_a
        target_file_b = command.file_b
        target_api_key = command.api_key
        target_eval_set_path = command.eval_set_path
        target_eval_set = command.eval_set
        target_sample_limit = command.sample_limit
        target_progress_cb = command.progress_callback

        with self.context.logger.span(
            "eval.compare",
            prompt_a=target_prompt_a,
            prompt_b=target_prompt_b,
            dry_run=target_dry_run,
        ):
            resolved_set_path = (
                self._resolve_eval_set_path(target_eval_set_path)
                if not target_eval_set
                else None
            )

            if target_file_a and target_file_b:
                data_a = (
                    self._reader.read_result_file(self.results_dir, target_file_a) or {}
                )
                data_b = (
                    self._reader.read_result_file(self.results_dir, target_file_b) or {}
                )
                res_a = data_a.get("results", {})
                res_b = data_b.get("results", {})
            else:
                completed_lock = threading.Lock()
                total_tracker = {"completed_total": 0}

                def run_a():
                    cb = self._build_compare_progress_callback(
                        label=target_prompt_a,
                        target_prompt_a=target_prompt_a,
                        target_prompt_b=target_prompt_b,
                        progress_cb=target_progress_cb,
                        lock=completed_lock,
                        total_tracker=total_tracker,
                    )
                    return harness_run_eval(
                        eval_set_path=resolved_set_path,
                        eval_set_data=target_eval_set,
                        prompt_version=target_prompt_a,
                        skip_scoring=target_dry_run,
                        api_key=target_api_key,
                        custom_prompt_template=target_custom_a,
                        sample_limit=target_sample_limit,
                        progress_callback=cb,
                    )

                def run_b():
                    cb = self._build_compare_progress_callback(
                        label=target_prompt_b,
                        target_prompt_a=target_prompt_a,
                        target_prompt_b=target_prompt_b,
                        progress_cb=target_progress_cb,
                        lock=completed_lock,
                        total_tracker=total_tracker,
                    )
                    return harness_run_eval(
                        eval_set_path=resolved_set_path,
                        eval_set_data=target_eval_set,
                        prompt_version=target_prompt_b,
                        skip_scoring=target_dry_run,
                        api_key=target_api_key,
                        custom_prompt_template=target_custom_b,
                        sample_limit=target_sample_limit,
                        progress_callback=cb,
                    )

                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                    fut_a = pool.submit(run_a)
                    fut_b = pool.submit(run_b)
                    res_a = fut_a.result()
                    res_b = fut_b.result()

                with self.context.db_service.get_connection() as conn:
                    self._writer.save_results(
                        res_a,
                        version=target_prompt_a,
                        out_dir=str(self.results_dir),
                        conn=conn,
                    )
                    self._writer.save_results(
                        res_b,
                        version=target_prompt_b,
                        out_dir=str(self.results_dir),
                        conn=conn,
                    )

            raw_comparison = generate_comparison_dict(res_a, res_b)
            self.context.logger.info(
                "Evaluation comparison completed",
                prompt_a=target_prompt_a,
                prompt_b=target_prompt_b,
            )

            metrics_a = EvalMetricDetails(**res_a)
            metrics_b = EvalMetricDetails(**res_b)
            comp_dto = PromptComparisonMetrics(
                prompt_a=target_prompt_a,
                prompt_b=target_prompt_b,
                accuracy_a=res_a.get("tier_accuracy", 0.0),
                accuracy_b=res_b.get("tier_accuracy", 0.0),
                accuracy_diff=round(
                    res_b.get("tier_accuracy", 0.0) - res_a.get("tier_accuracy", 0.0),
                    4,
                ),
                macro_f1_a=res_a.get("macro_f1", 0.0),
                macro_f1_b=res_b.get("macro_f1", 0.0),
                macro_f1_diff=round(
                    res_b.get("macro_f1", 0.0) - res_a.get("macro_f1", 0.0),
                    4,
                ),
                score_mae_a=res_a.get("score_mae", 0.0),
                score_mae_b=res_b.get("score_mae", 0.0),
                score_mae_diff=round(
                    res_b.get("score_mae", 0.0) - res_a.get("score_mae", 0.0),
                    4,
                ),
                critical_recall_a=res_a.get("critical_threat_recall", 0.0),
                critical_recall_b=res_b.get("critical_threat_recall", 0.0),
                critical_recall_diff=round(
                    res_b.get("critical_threat_recall", 0.0)
                    - res_a.get("critical_threat_recall", 0.0),
                    4,
                ),
                tier_consistency_a=res_a.get("score_tier_consistency", 0.0),
                tier_consistency_b=res_b.get("score_tier_consistency", 0.0),
                tier_consistency_diff=round(
                    res_b.get("score_tier_consistency", 0.0)
                    - res_a.get("score_tier_consistency", 0.0),
                    4,
                ),
                tier_distribution_comparison=raw_comparison.get("tier_comparisons", {}),
            )

            return EvalCompareResult(
                success=True,
                comparison=comp_dto,
                results_a=metrics_a,
                results_b=metrics_b,
                timestamp=datetime.now().isoformat(),
            )

    def list_history(self) -> List[EvalHistoryItem]:
        return self._reader.list_history(self.results_dir)

    def get_result_file(self, filename: str) -> Optional[Dict[str, Any]]:
        return self._reader.read_result_file(self.results_dir, filename)

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

        eval_command = RunEvalCommand(
            prompt_version=prompt_version,
            custom_prompt_template=custom_prompt_template,
            dry_run=dry_run,
            api_key=api_key,
            eval_set_path=eval_set_path,
            eval_set=eval_set,
            sample_limit=sample_limit,
            progress_callback=progress_callback,
        )

        eval_output = self.run_eval(eval_command)

        return {
            "results": eval_output.model_dump(),
            "metadata": {
                "prompt_version": prompt_version,
                "dry_run": dry_run,
                "total_samples": eval_output.results.total,
                "tier_accuracy": eval_output.results.tier_accuracy,
                "saved_file": eval_output.saved_file,
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

        compare_command = ComparePromptsCommand(
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

        compare_output = self.compare_prompts(compare_command)

        return {
            "results": compare_output.model_dump(),
            "metadata": {
                "prompt_a": prompt_a,
                "prompt_b": prompt_b,
                "dry_run": dry_run,
            },
        }

    # =========================================================================
    # Private Helpers
    # =========================================================================

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

    def _build_compare_progress_callback(
        self,
        label: str,
        target_prompt_a: str,
        target_prompt_b: str,
        progress_cb: Optional[Any],
        lock: threading.Lock,
        total_tracker: Dict[str, int],
    ) -> Optional[Any]:
        if not progress_cb:
            return None

        last_reported = 0

        def cb(
            curr: int,
            tot: int,
            meta: Optional[Dict[str, Any]] = None,
            partial: Optional[Any] = None,
        ) -> None:
            nonlocal last_reported
            with lock:
                delta = curr - last_reported
                last_reported = curr
                total_tracker["completed_total"] += delta
                total_expected = 2 * tot if tot > 0 else 2
                try:
                    progress_cb(
                        total_tracker["completed_total"],
                        total_expected,
                        {
                            "stage": f"Evaluating {label}",
                            "prompt_a": target_prompt_a,
                            "prompt_b": target_prompt_b,
                            "completed_total": total_tracker["completed_total"],
                            "total_expected": total_expected,
                        },
                        None,
                    )
                except Exception as cb_exc:
                    self.context.logger.debug(
                        f"Compare progress callback error: {cb_exc}"
                    )

        return cb
