import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlmodel import Session, col, select

from src.services.database.dependencies import get_db_connection, get_db_session
from src.services.eval.internals.repositories.models import EvalRunTable
from src.services.eval.protocols import IEvalReader
from src.services.eval.types import EvalHistoryItem
from src.services.logger.logger_service import get_logger
from src.services.prompts.templates import CANONICAL_PROMPTS_LIST

logger = get_logger("eval.reader")


def _get_session(conn: Any) -> Session:
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

    def get_runs(
        self,
        conn: Any,
        prompt_version: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
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

    def list_prompts(self, prompts_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
        return CANONICAL_PROMPTS_LIST

    def list_history(self, results_dir: Path) -> List[EvalHistoryItem]:
        history: List[EvalHistoryItem] = []
        try:
            with get_db_connection() as conn:
                with _get_session(conn) as session:
                    statement = (
                        select(EvalRunTable)
                        .order_by(col(EvalRunTable.created_at).desc())
                        .limit(100)
                    )
                    rows = session.exec(statement).all()
                    for r in rows:
                        history.append(
                            EvalHistoryItem(
                                run_id=r.run_id,
                                prompt_version=r.prompt_version,
                                total_samples=r.total_samples,
                                tier_accuracy=r.tier_accuracy,
                                macro_f1=r.macro_f1,
                                critical_threat_recall=r.critical_threat_recall,
                                created_at=r.created_at,
                                filename=r.run_id,
                            )
                        )
        except Exception as e:
            logger.warning(f"Error querying eval_runs database table: {e}")

        if not history and results_dir.exists():
            for p in results_dir.glob("*.json"):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        res = data.get("results", {})
                        history.append(
                            EvalHistoryItem(
                                run_id=p.stem,
                                prompt_version=data.get("prompt_version", "v2.0"),
                                total_samples=res.get("total", 0),
                                tier_accuracy=res.get("tier_accuracy", 0.0),
                                macro_f1=res.get("macro_f1", 0.0),
                                critical_threat_recall=res.get(
                                    "critical_threat_recall", 0.0
                                ),
                                created_at=data.get("timestamp"),
                                filename=p.name,
                            )
                        )
                except Exception as ex:
                    logger.warning(f"Failed to read result file {p}: {ex}")

        return sorted(history, key=lambda x: str(x.created_at or ""), reverse=True)

    def get_history_file(
        self, results_dir: Path, filename: str
    ) -> Optional[Dict[str, Any]]:
        return self.read_result_file(results_dir, filename)

    def read_result_file(
        self, results_dir: Path, filename: str
    ) -> Optional[Dict[str, Any]]:
        clean_filename = Path(filename).name
        target = results_dir / clean_filename
        if target.exists():
            try:
                with open(target, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to read result file {target}: {e}")
                return None

        try:
            with get_db_connection() as conn:
                with _get_session(conn) as session:
                    statement = select(EvalRunTable).where(
                        EvalRunTable.run_id == clean_filename
                    )
                    row = session.exec(statement).first()
                    if row and row.results_json:
                        return json.loads(row.results_json)
        except Exception as e:
            logger.warning(f"Error reading result file from database: {e}")

        return None
