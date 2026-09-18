import time
import secrets
from datetime import datetime
from typing import List, Dict, Any, Optional

from src.services.database import (
    get_dynamo_resource,
    get_table_name,
    float_to_decimal,
    decimal_to_python,
    is_deployed,
)
from src.services.logger import get_logger

logger = get_logger("services.eval.dynamo")


class DynamoEvalRepository:
    def __init__(self, table_name: Optional[str] = None):
        self._table_name = table_name or get_table_name("eval_runs")

    def _get_table(self):
        return get_dynamo_resource().Table(self._table_name)

    def save_results(self, results: dict, version: str = "v1.0", out_dir: Optional[str] = None) -> str:
        clean_version = version.replace(".", "_")
        run_id = f"eval-results-{clean_version}-{int(time.time())}"
        timestamp = datetime.now().isoformat()

        item = {
            "run_id": run_id,
            "filename": f"{run_id}.json",
            "prompt_version": version,
            "timestamp": timestamp,
            "total": results.get("total", 0),
            "tier_accuracy": results.get("tier_accuracy", 0),
            "macro_f1": results.get("macro_f1", 0),
            "weighted_f1": results.get("weighted_f1", 0),
            "score_mae": results.get("score_mae", 0),
            "within_5_points_pct": results.get("within_5_points_pct", 0),
            "results": results,
            "created_at": timestamp,
        }

        with logger.span("dynamo.save_eval_results", run_id=run_id, version=version):
            table = self._get_table()
            table.put_item(Item=float_to_decimal(item))
            logger.info("Persisted eval run to DynamoDB", run_id=run_id, prompt_version=version)

        return run_id

    def list_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        with logger.span("dynamo.list_eval_history"):
            table = self._get_table()
            response = table.scan(Limit=limit)
            items = response.get("Items", [])
            py_items = [decimal_to_python(item) for item in items]
            py_items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return py_items

    def get_result_file(self, filename_or_id: str) -> Dict[str, Any]:
        run_id = filename_or_id.replace(".json", "")
        with logger.span("dynamo.get_eval_result", run_id=run_id):
            table = self._get_table()
            response = table.get_item(Key={"run_id": run_id})
            item = response.get("Item")
            if not item:
                raise FileNotFoundError(f"Eval result run '{filename_or_id}' not found in DynamoDB")
            py_item = decimal_to_python(item)
            return {
                "timestamp": py_item.get("timestamp"),
                "prompt_version": py_item.get("prompt_version"),
                "results": py_item.get("results", {}),
            }
