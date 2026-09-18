import json
import time
from pathlib import Path
from datetime import datetime
from src.services.database import (
    get_db_connection,
    is_deployed,
    get_dynamo_resource,
    get_table_name,
    float_to_decimal,
)
from src.services.eval.eval_types import IEvalWriter
from src.services.logger import get_logger

logger = get_logger("eval.writer")


class EvalWriter(IEvalWriter):
    def save_results(self, results: dict, version: str = "v1.0", out_dir: str = "results") -> Path:
        clean_version = version.replace(".", "_")
        run_id = f"eval-results-{clean_version}-{int(time.time())}.json"
        now_iso = datetime.now().isoformat()

        total = results.get("total", 0)
        tier_accuracy = float(results.get("tier_accuracy", 0.0))
        macro_f1 = float(results.get("macro_f1", 0.0))
        weighted_f1 = float(results.get("weighted_f1", 0.0))
        critical_threat_recall = float(results.get("critical_threat_recall", 0.0))
        score_tier_consistency = float(results.get("score_tier_consistency", 0.0))
        score_mae = float(results.get("score_mae", 0.0))
        score_rmse = float(results.get("score_rmse", 0.0))
        within_5_points = int(results.get("within_5_points", 0))
        within_5_points_pct = float(results.get("within_5_points_pct", 0.0))
        tier_metrics_json = json.dumps(results.get("tier_metrics", {}))
        predictions_json = json.dumps(results.get("predictions", []))
        results_json = json.dumps({
            "timestamp": now_iso,
            "prompt_version": version,
            "results": results,
        })

        # 1. DynamoDB persistence if deployed
        if is_deployed():
            try:
                table = get_dynamo_resource().Table(get_table_name("eval_runs"))
                item = {
                    "run_id": run_id,
                    "prompt_version": version,
                    "total_samples": total,
                    "tier_accuracy": float_to_decimal(tier_accuracy),
                    "macro_f1": float_to_decimal(macro_f1),
                    "weighted_f1": float_to_decimal(weighted_f1),
                    "critical_threat_recall": float_to_decimal(critical_threat_recall),
                    "score_tier_consistency": float_to_decimal(score_tier_consistency),
                    "score_mae": float_to_decimal(score_mae),
                    "score_rmse": float_to_decimal(score_rmse),
                    "within_5_points": within_5_points,
                    "within_5_points_pct": float_to_decimal(within_5_points_pct),
                    "tier_metrics_json": tier_metrics_json,
                    "predictions_json": predictions_json,
                    "results_json": results_json,
                    "created_at": now_iso,
                }
                table.put_item(Item=item)
                logger.info("Saved evaluation run to DynamoDB table eval_runs", run_id=run_id)
                return Path(run_id)
            except Exception as e:
                logger.warning(f"DynamoDB eval write skipped / failed: {e}. Falling back to SQLite.")

        # 2. Relational SQLite persistence (Local / Primary fallback)
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO eval_runs (
                        run_id, prompt_version, total_samples, tier_accuracy, macro_f1,
                        weighted_f1, critical_threat_recall, score_tier_consistency,
                        score_mae, score_rmse, within_5_points, within_5_points_pct,
                        tier_metrics_json, predictions_json, results_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id, version, total, tier_accuracy, macro_f1,
                        weighted_f1, critical_threat_recall, score_tier_consistency,
                        score_mae, score_rmse, within_5_points, within_5_points_pct,
                        tier_metrics_json, predictions_json, results_json, now_iso,
                    ),
                )
                conn.commit()
                logger.info("Saved evaluation run to database table eval_runs", run_id=run_id)
        except Exception as e:
            logger.error(f"Failed to persist eval run to database: {e}")

        return Path(run_id)
