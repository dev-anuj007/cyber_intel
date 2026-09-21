"""Eval Data Reader Repository with SQLModel ORM."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlmodel import Session, col, select

from src.services.database import get_db_connection, get_db_session
from src.services.eval.eval_types import IEvalReader
from src.services.eval.repositories.models import EvalRunTable
from src.services.logger import get_logger
from src.services.prompts import CANONICAL_PROMPTS_LIST

logger = get_logger("eval.reader")


def _get_session(conn) -> Session:
    return get_db_session(conn=conn)


class EvalReader(IEvalReader):
    def get_run_by_id(self, conn: Any, run_id: str) -> Optional[Dict[str, Any]]:
        with _get_session(conn) as session:
            statement = select(EvalRunTable).where(EvalRunTable.run_id == run_id)
            row = session.exec(statement).first()
            if not row:
                return None
            return {
                "run_id": row.run_id,
                "prompt_version": row.prompt_version,
                "accuracy": row.tier_accuracy,
                "tier_accuracy": row.tier_accuracy,
                "f1_score": row.macro_f1,
                "macro_f1": row.macro_f1,
                "recall": row.critical_threat_recall,
                "critical_threat_recall": row.critical_threat_recall,
                "sample_size": row.total_samples,
                "total_samples": row.total_samples,
                "metrics_json": row.tier_metrics_json,
                "created_at": row.created_at,
            }

    def get_runs(self, conn: Any, prompt_version: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        with _get_session(conn) as session:
            query = select(EvalRunTable)
            if prompt_version:
                query = query.where(EvalRunTable.prompt_version == prompt_version)
            rows = session.exec(query.limit(limit)).all()
            return [
                {
                    "run_id": r.run_id,
                    "prompt_version": r.prompt_version,
                    "accuracy": r.tier_accuracy,
                    "f1_score": r.macro_f1,
                }
                for r in rows
            ]

    def list_prompts(self, prompts_dir: Path) -> List[Dict[str, Any]]:
        return CANONICAL_PROMPTS_LIST

    def list_history(self, results_dir: Path) -> List[Dict[str, Any]]:
        history = []
        try:
            with get_db_connection() as conn:
                with _get_session(conn) as session:
                    statement = select(EvalRunTable).order_by(col(EvalRunTable.created_at).desc()).limit(100)
                    rows = session.exec(statement).all()
                    for r in rows:
                        history.append(
                            {
                                "filename": r.run_id,
                                "prompt_version": r.prompt_version,
                                "total": r.total_samples,
                                "tier_accuracy": r.tier_accuracy,
                                "macro_f1": r.macro_f1,
                                "weighted_f1": r.weighted_f1,
                                "score_mae": r.score_mae,
                                "within_5_points_pct": r.within_5_points_pct,
                                "timestamp": r.created_at,
                            }
                        )
        except Exception as e:
            logger.warning(f"Error querying eval_runs database table: {e}")

        # Fallback to local files if database is empty
        if not history and results_dir.exists():
            for p in results_dir.glob("*.json"):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        res = data.get("results", {})
                        history.append(
                            {
                                "filename": p.name,
                                "prompt_version": data.get("prompt_version", "v2.0"),
                                "total": res.get("total", 0),
                                "tier_accuracy": res.get("tier_accuracy", 0.0),
                                "macro_f1": res.get("macro_f1", 0.0),
                                "weighted_f1": res.get("weighted_f1", 0.0),
                                "score_mae": res.get("score_mae", 0.0),
                                "within_5_points_pct": res.get("within_5_points_pct", 0.0),
                                "timestamp": data.get("timestamp", ""),
                            }
                        )
                except Exception:
                    pass
            history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        return history

    def read_result_file(self, results_dir: Path, filename: str) -> Optional[Dict[str, Any]]:
        return self.get_history_file(results_dir, filename)

    def get_history_file(self, results_dir: Path, filename: str) -> Optional[Dict[str, Any]]:
        clean_filename = filename.replace(".json", "")

        # Database lookup
        try:
            with get_db_connection() as conn:
                with _get_session(conn) as session:
                    statement = select(EvalRunTable).where(
                        (EvalRunTable.run_id == filename)
                        | (EvalRunTable.run_id == f"{clean_filename}.json")
                        | (EvalRunTable.run_id == clean_filename)
                    )
                    row = session.exec(statement).first()
                    if row:
                        if row.results_json:
                            try:
                                return json.loads(row.results_json)
                            except Exception:
                                pass
                        return {
                            "timestamp": row.created_at,
                            "prompt_version": row.prompt_version,
                            "results": {
                                "total": row.total_samples,
                                "tier_accuracy": row.tier_accuracy,
                                "macro_f1": row.macro_f1,
                                "weighted_f1": row.weighted_f1,
                                "critical_threat_recall": row.critical_threat_recall,
                                "score_tier_consistency": row.score_tier_consistency,
                                "score_mae": row.score_mae,
                                "score_rmse": row.score_rmse,
                                "within_5_points": row.within_5_points,
                                "within_5_points_pct": row.within_5_points_pct,
                                "tier_metrics": json.loads(row.tier_metrics_json) if row.tier_metrics_json else {},
                                "predictions": json.loads(row.predictions_json) if row.predictions_json else [],
                            },
                        }
        except Exception as e:
            logger.warning(f"Database lookup failed for eval run {clean_filename}: {e}")

        # Local file fallback
        for target in [results_dir / filename, results_dir / f"{clean_filename}.json"]:
            if target.exists():
                try:
                    with open(target, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    pass

        return None
