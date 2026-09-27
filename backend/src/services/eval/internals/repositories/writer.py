import json
import secrets
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlmodel import Session

from src.services.database.dependencies import get_db_connection, get_db_session
from src.services.eval.internals.repositories.models import EvalRunTable
from src.services.eval.protocols import IEvalWriter
from src.services.logger.logger_service import get_logger

logger = get_logger("eval.writer")


def _get_session(conn: Any) -> Session:
    return get_db_session(conn=conn)


class EvalWriter(IEvalWriter):
    def save_run(self, conn: Any, run_record: dict) -> str:
        with _get_session(conn) as session:
            record = EvalRunTable(
                run_id=run_record["run_id"],
                prompt_version=run_record.get("prompt_version", "v2.0"),
                total_samples=run_record.get(
                    "sample_size", run_record.get("total_samples", 0)
                ),
                tier_accuracy=float(
                    run_record.get("accuracy", run_record.get("tier_accuracy", 0.0))
                ),
                macro_f1=float(
                    run_record.get("f1_score", run_record.get("macro_f1", 0.0))
                ),
                weighted_f1=float(run_record.get("weighted_f1", 0.0)),
                critical_threat_recall=float(
                    run_record.get(
                        "recall",
                        run_record.get("critical_threat_recall", 0.0),
                    )
                ),
                score_tier_consistency=float(
                    run_record.get("score_tier_consistency", 0.0)
                ),
                score_mae=float(run_record.get("score_mae", 0.0)),
                score_rmse=float(run_record.get("score_rmse", 0.0)),
                within_5_points=int(run_record.get("within_5_points", 0)),
                within_5_points_pct=float(run_record.get("within_5_points_pct", 0.0)),
                tier_metrics_json=run_record.get("metrics_json", "{}"),
                predictions_json=json.dumps(run_record.get("predictions", [])),
                results_json=json.dumps(run_record),
                created_at=run_record.get("created_at", datetime.now().isoformat()),
            )
            session.add(record)
            session.commit()
            return record.run_id

    def save_results(
        self,
        results: dict,
        version: str = "v1.0",
        out_dir: str = "results",
        conn: Optional[Any] = None,
    ) -> Path:
        clean_version = version.replace(".", "_")
        run_id = f"eval-results-{clean_version}-{int(time.time())}_{secrets.token_hex(4)}.json"
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
        results_json = json.dumps(
            {
                "timestamp": now_iso,
                "prompt_version": version,
                "results": results,
            }
        )

        try:
            db_conn = conn if conn is not None else get_db_connection()
            with db_conn as active_conn:
                with _get_session(active_conn) as session:
                    eval_record = EvalRunTable(
                        run_id=run_id,
                        prompt_version=version,
                        total_samples=total,
                        tier_accuracy=tier_accuracy,
                        macro_f1=macro_f1,
                        weighted_f1=weighted_f1,
                        critical_threat_recall=critical_threat_recall,
                        score_tier_consistency=score_tier_consistency,
                        score_mae=score_mae,
                        score_rmse=score_rmse,
                        within_5_points=within_5_points,
                        within_5_points_pct=within_5_points_pct,
                        tier_metrics_json=tier_metrics_json,
                        predictions_json=predictions_json,
                        results_json=results_json,
                        created_at=now_iso,
                    )
                    session.add(eval_record)
                    session.commit()
                    logger.info(
                        "Saved evaluation run to database table eval_runs",
                        run_id=run_id,
                    )
        except Exception as e:
            logger.error(f"Failed to persist eval run to database: {e}")

        return Path(run_id)
