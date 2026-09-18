import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from src.core.config import ROOT_DIR
from src.services.eval.eval_types import IEvalService, IEvalReader, IEvalWriter
from src.services.eval.repositories.reader import EvalReader
from src.services.eval.repositories.writer import EvalWriter
from src.services.eval.repositories.dynamo_eval import DynamoEvalRepository
from src.services.prompts.prompt_service import PromptService, default_prompt_service
from src.services.eval.eval_harness import (
    run_eval as harness_run_eval,
    generate_comparison_dict,
)
from src.services.database import is_deployed
from src.services.logger import get_logger

logger = get_logger("services.eval")


class EvalService(IEvalService):
    def __init__(
        self,
        evals_dir: Optional[Path] = None,
        reader: Optional[IEvalReader] = None,
        writer: Optional[IEvalWriter] = None,
        prompt_service: Optional[PromptService] = None,
    ):
        self.root_dir = ROOT_DIR
        self.evals_dir = evals_dir or Path(__file__).resolve().parent
        self.prompt_service = prompt_service or default_prompt_service

        if is_deployed() and (reader is None or writer is None):
            self.dynamo_eval_repo = DynamoEvalRepository()
            self.reader = reader or self.dynamo_eval_repo
            self.writer = writer or self.dynamo_eval_repo
        else:
            self.dynamo_eval_repo = None
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
    ) -> Dict[str, Any]:
        with logger.span("eval.compare", prompt_a=prompt_a, prompt_b=prompt_b, dry_run=dry_run):
            target_set_path = self._resolve_eval_set_path(eval_set_path) if not eval_set else None

            if file_a and file_b:
                res_a = self.reader.read_result_file(self.results_dir, file_a)["results"]
                res_b = self.reader.read_result_file(self.results_dir, file_b)["results"]
            else:
                res_a = harness_run_eval(
                    eval_set_path=target_set_path,
                    eval_set_data=eval_set,
                    prompt_version=prompt_a,
                    skip_scoring=dry_run,
                    api_key=api_key,
                    custom_prompt_template=custom_prompt_a,
                    sample_limit=sample_limit,
                )
                self.writer.save_results(res_a, version=prompt_a, out_dir=str(self.results_dir))

                res_b = harness_run_eval(
                    eval_set_path=target_set_path,
                    eval_set_data=eval_set,
                    prompt_version=prompt_b,
                    skip_scoring=dry_run,
                    api_key=api_key,
                    custom_prompt_template=custom_prompt_b,
                    sample_limit=sample_limit,
                )
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

    def list_history(self) -> List[Dict[str, Any]]:
        return self.reader.list_history(self.results_dir)

    def get_result_file(self, filename: str) -> Dict[str, Any]:
        return self.reader.read_result_file(self.results_dir, filename)


default_eval_service = EvalService()
