import json
from typing import Any, List, Optional

from sqlmodel import Session, col, or_, select

from src.services.database.dependencies import get_db_session
from src.services.scorer.internals.repositories.models import AIScoreTable
from src.services.scorer.protocols import IScoreReader


def _get_session(conn: Any) -> Session:
    return get_db_session(conn=conn)


def _extract_base_domain(account_key: str) -> str:
    clean = (account_key or "").strip()
    if clean.startswith("domain:"):
        clean = clean[7:]
    parts = clean.split(":")
    return parts[0].strip().lower()


class ScoreReader(IScoreReader):
    def get_latest_score(self, conn: Any, account_key: str, version: Optional[str] = None) -> Optional[dict]:
        base_dom = _extract_base_domain(account_key)
        target_version = version
        if not target_version and account_key.count(":") >= 2:
            parts = account_key.split(":")
            if parts[-1].startswith("v") and parts[-1][1:].isdigit():
                target_version = parts[-1]

        with _get_session(conn) as session:
            if target_version:
                v_tag = target_version.lower()
                candidate_keys = [f"domain:{base_dom}:{v_tag}", f"{base_dom}:{v_tag}"]
                if v_tag == "v1":
                    candidate_keys.extend([f"domain:{base_dom}", base_dom, f"domain:{base_dom}:v1", f"{base_dom}:v1"])
                statement = (
                    select(AIScoreTable)
                    .where(
                        col(AIScoreTable.account_key).in_(candidate_keys),
                        AIScoreTable.is_latest == 1,
                    )
                    .order_by(col(AIScoreTable.version).desc(), col(AIScoreTable.id).desc())
                    .limit(1)
                )
                row = session.exec(statement).first()
                if not row:
                    statement_fallback = (
                        select(AIScoreTable)
                        .where(col(AIScoreTable.account_key).in_(candidate_keys))
                        .order_by(col(AIScoreTable.version).desc(), col(AIScoreTable.id).desc())
                        .limit(1)
                    )
                    row = session.exec(statement_fallback).first()
            else:
                statement = (
                    select(AIScoreTable)
                    .where(
                        or_(
                            AIScoreTable.account_key == account_key,
                            AIScoreTable.account_key == f"domain:{account_key}",
                            AIScoreTable.account_key == account_key.replace("domain:", ""),
                            AIScoreTable.account_key == f"domain:{base_dom}",
                            AIScoreTable.account_key == base_dom,
                            col(AIScoreTable.account_key).like(f"domain:{base_dom}:v%"),
                            col(AIScoreTable.account_key).like(f"{base_dom}:v%"),
                        ),
                        AIScoreTable.is_latest == 1,
                    )
                    .order_by(col(AIScoreTable.version).desc(), col(AIScoreTable.id).desc())
                    .limit(1)
                )
                row = session.exec(statement).first()
                if not row:
                    fallback = (
                        select(AIScoreTable)
                        .where(
                            or_(
                                AIScoreTable.account_key == account_key,
                                AIScoreTable.account_key == f"domain:{account_key}",
                                AIScoreTable.account_key == account_key.replace("domain:", ""),
                                AIScoreTable.account_key == f"domain:{base_dom}",
                                AIScoreTable.account_key == base_dom,
                                col(AIScoreTable.account_key).like(f"domain:{base_dom}:v%"),
                                col(AIScoreTable.account_key).like(f"{base_dom}:v%"),
                            )
                        )
                        .order_by(col(AIScoreTable.version).desc(), col(AIScoreTable.id).desc())
                        .limit(1)
                    )
                    row = session.exec(fallback).first()

            if not row:
                return None
            return self._format_ai_score_model(row)

    def get_score_history(self, conn: Any, account_key: str, version: Optional[str] = None) -> List[dict]:
        base_dom = _extract_base_domain(account_key)
        target_version = version
        if not target_version and account_key.count(":") >= 2:
            parts = account_key.split(":")
            if parts[-1].startswith("v") and parts[-1][1:].isdigit():
                target_version = parts[-1]

        with _get_session(conn) as session:
            if target_version:
                v_tag = target_version.lower()
                candidate_keys = [f"domain:{base_dom}:{v_tag}", f"{base_dom}:{v_tag}"]
                if v_tag == "v1":
                    candidate_keys.extend([f"domain:{base_dom}", base_dom, f"domain:{base_dom}:v1", f"{base_dom}:v1"])
                statement = (
                    select(AIScoreTable)
                    .where(col(AIScoreTable.account_key).in_(candidate_keys))
                    .order_by(col(AIScoreTable.version).desc(), col(AIScoreTable.id).desc())
                )
            else:
                statement = (
                    select(AIScoreTable)
                    .where(
                        or_(
                            AIScoreTable.account_key == account_key,
                            AIScoreTable.account_key == f"domain:{account_key}",
                            AIScoreTable.account_key == account_key.replace("domain:", ""),
                            AIScoreTable.account_key == f"domain:{base_dom}",
                            AIScoreTable.account_key == base_dom,
                            col(AIScoreTable.account_key).like(f"domain:{base_dom}:v%"),
                            col(AIScoreTable.account_key).like(f"{base_dom}:v%"),
                        )
                    )
                    .order_by(col(AIScoreTable.version).desc(), col(AIScoreTable.id).desc())
                )
            rows = session.exec(statement).all()
            return [self._format_ai_score_model(r) for r in rows]

    def _format_ai_score_model(self, model: AIScoreTable) -> dict:
        raw_risks = getattr(model, "key_risks_json", None) or getattr(model, "key_risks", None)
        try:
            risks = json.loads(raw_risks) if isinstance(raw_risks, str) else raw_risks
        except Exception:
            risks = [raw_risks] if raw_risks else []

        raw_tokens = getattr(model, "tokens_used_json", None) or getattr(model, "tokens_used", None)
        try:
            tokens = json.loads(raw_tokens) if isinstance(raw_tokens, str) else raw_tokens
        except Exception:
            tokens = {}

        return {
            "id": model.id,
            "account_key": model.account_key,
            "version": model.version,
            "score": model.score,
            "priority_tier": model.priority_tier,
            "key_risks": risks,
            "suggested_outreach": model.suggested_outreach,
            "score_rationale": model.score_rationale,
            "model_version": model.model_version,
            "model_name": model.model_name,
            "tokens_used": tokens,
            "latency_ms": model.latency_ms,
            "cost_usd": model.cost_usd,
            "timestamp": model.scored_at,
        }
