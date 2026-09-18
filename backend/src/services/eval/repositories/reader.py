import json
import os
from pathlib import Path
from typing import List, Dict, Any
from src.services.eval.eval_types import IEvalReader
from src.services.database import (
    get_db_connection,
    is_deployed,
    get_dynamo_resource,
    get_table_name,
    decimal_to_python,
)
from src.services.prompts import CANONICAL_PROMPTS_LIST
from src.services.logger import get_logger

logger = get_logger("eval.reader")


class EvalReader(IEvalReader):
    def list_prompts(self, prompts_dir: Path) -> List[Dict[str, Any]]:
        return CANONICAL_PROMPTS_LIST

    def list_history(self, results_dir: Path) -> List[Dict[str, Any]]:
        history = []

        # 1. DynamoDB if deployed
        if is_deployed():
            try:
                table = get_dynamo_resource().Table(get_table_name("eval_runs"))
                response = table.scan(Limit=100)
                items = response.get("Items", [])
                if items:
                    for item in items:
                        py_item = decimal_to_python(item)
                        history.append({
                            "filename": py_item.get("run_id", ""),
                            "prompt_version": py_item.get("prompt_version", "v2.0"),
                            "total": int(py_item.get("total_samples", 25)),
                            "tier_accuracy": float(py_item.get("tier_accuracy", 0.0)),
                            "macro_f1": float(py_item.get("macro_f1", 0.0)),
                            "weighted_f1": float(py_item.get("weighted_f1", 0.0)),
                            "score_mae": float(py_item.get("score_mae", 0.0)),
                            "within_5_points_pct": float(py_item.get("within_5_points_pct", 0.0)),
                            "timestamp": str(py_item.get("created_at", "")),
                        })
                    history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
                    return history
            except Exception as e:
                logger.warning(f"DynamoDB eval history scan skipped / failed: {e}")

        # 2. SQLite relational database (Local / Primary fallback)
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT run_id, prompt_version, total_samples, tier_accuracy,
                           macro_f1, weighted_f1, score_mae, within_5_points_pct, created_at
                    FROM eval_runs
                    ORDER BY id DESC
                    LIMIT 100
                    """
                )
                rows = cursor.fetchall()
                for r in rows:
                    history.append({
                        "filename": r[0],
                        "prompt_version": r[1],
                        "total": r[2],
                        "tier_accuracy": float(r[3]),
                        "macro_f1": float(r[4]),
                        "weighted_f1": float(r[5]),
                        "score_mae": float(r[6]),
                        "within_5_points_pct": float(r[7]),
                        "timestamp": str(r[8]),
                    })
        except Exception as e:
            logger.warning(f"Error querying eval_runs database table: {e}")

        # If DB history is empty, check and import legacy disk files into DB
        if not history and results_dir and results_dir.exists():
            self._import_disk_files_to_db(results_dir)
            return self.list_history(results_dir)

        return history

    def _import_disk_files_to_db(self, results_dir: Path) -> None:
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                for file_path in sorted(results_dir.glob("eval-results-*.json"), key=os.path.getmtime, reverse=True):
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            res = data.get("results", {})
                            run_id = file_path.name
                            version = data.get("prompt_version", res.get("prompt_version", "v2.0"))
                            total = res.get("total", 25)
                            tier_acc = float(res.get("tier_accuracy", 0.0))
                            macro_f1 = float(res.get("macro_f1", 0.0))
                            weighted_f1 = float(res.get("weighted_f1", 0.0))
                            recall = float(res.get("critical_threat_recall", 0.0))
                            consistency = float(res.get("score_tier_consistency", 0.0))
                            score_mae = float(res.get("score_mae", 0.0))
                            score_rmse = float(res.get("score_rmse", 0.0))
                            within_5 = int(res.get("within_5_points", 0))
                            within_5_pct = float(res.get("within_5_points_pct", 0.0))
                            tier_metrics_json = json.dumps(res.get("tier_metrics", {}))
                            predictions_json = json.dumps(res.get("predictions", []))
                            results_json = json.dumps(data)
                            ts = data.get("timestamp", "")

                            cursor.execute(
                                """
                                INSERT OR IGNORE INTO eval_runs (
                                    run_id, prompt_version, total_samples, tier_accuracy, macro_f1,
                                    weighted_f1, critical_threat_recall, score_tier_consistency,
                                    score_mae, score_rmse, within_5_points, within_5_points_pct,
                                    tier_metrics_json, predictions_json, results_json, created_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    run_id, version, total, tier_acc, macro_f1,
                                    weighted_f1, recall, consistency,
                                    score_mae, score_rmse, within_5, within_5_pct,
                                    tier_metrics_json, predictions_json, results_json, ts,
                                ),
                            )
                    except Exception as err:
                        logger.warning(f"Skipping legacy file {file_path}: {err}")
                conn.commit()
                logger.info("Migrated legacy evaluation runs from disk to database table eval_runs")
        except Exception as e:
            logger.warning(f"Error migrating legacy eval files: {e}")

    def read_result_file(self, results_dir: Path, filename: str) -> Dict[str, Any]:
        clean_filename = os.path.basename(filename)

        # 1. Try DynamoDB if deployed
        if is_deployed():
            try:
                table = get_dynamo_resource().Table(get_table_name("eval_runs"))
                response = table.get_item(Key={"run_id": clean_filename})
                item = response.get("Item")
                if item and "results_json" in item:
                    return json.loads(item["results_json"])
            except Exception as e:
                logger.warning(f"DynamoDB lookup failed for eval run {clean_filename}: {e}")

        # 2. Try SQLite database
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT results_json FROM eval_runs WHERE run_id = ? OR run_id LIKE ? LIMIT 1",
                    (clean_filename, f"%{clean_filename}%"),
                )
                row = cursor.fetchone()
                if row and row[0]:
                    return json.loads(row[0])
        except Exception as e:
            logger.warning(f"Database lookup failed for eval run {clean_filename}: {e}")

        # 3. Fallback to file if needed
        candidate_paths = [
            results_dir / clean_filename,
            Path("/tmp/evals/results") / clean_filename,
        ]
        for file_path in candidate_paths:
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)

        raise FileNotFoundError(f"Eval result '{clean_filename}' not found in database or disk")
