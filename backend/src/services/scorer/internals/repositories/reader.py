import json
from typing import Any, List, Optional

from sqlmodel import Session, and_, col, or_, select

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
    def get_latest_score(
        self, conn: Any, account_key: str, version: Optional[str] = None
    ) -> Optional[dict]:
        base_dom = _extract_base_domain(account_key)
        target_version = version
        if not target_version and account_key.count(":") >= 2:
            parts = account_key.split(":")
            if parts[-1].startswith("v") and parts[-1][1:].isdigit():
                target_version = parts[-1]

        with _get_session(conn) as session:
            candidate_keys = [
                account_key,
                f"domain:{account_key}",
                account_key.replace("domain:", ""),
                f"domain:{base_dom}",
                base_dom,
            ]
            v_num = None
            if target_version:
                v_tag = target_version.lower()
                clean_num_str = v_tag.replace("v", "")
                v_num = int(clean_num_str) if clean_num_str.isdigit() else None
                candidate_keys.extend(
                    [
                        f"domain:{base_dom}:{v_tag}",
                        f"{base_dom}:{v_tag}",
                        f"domain:{account_key}:{v_tag}",
                        f"{account_key}:{v_tag}",
                    ]
                )
                if v_tag == "v1":
                    candidate_keys.extend(
                        [
                            f"domain:{base_dom}:v1",
                            f"{base_dom}:v1",
                        ]
                    )

            conditions: List[Any] = [
                col(AIScoreTable.account_key).in_(candidate_keys),
                col(AIScoreTable.account_key).like(f"domain:{base_dom}:v%"),
                col(AIScoreTable.account_key).like(f"{base_dom}:v%"),
            ]
            if v_num is not None:
                conditions.append(
                    and_(
                        col(AIScoreTable.account_key).in_(
                            [f"domain:{base_dom}", base_dom]
                        ),
                        AIScoreTable.version == v_num,
                    )
                )

            statement = (
                select(AIScoreTable)
                .where(
                    or_(*conditions),
                    AIScoreTable.is_latest == 1,
                )
                .order_by(
                    col(AIScoreTable.version).desc(),
                    col(AIScoreTable.id).desc(),
                )
                .limit(1)
            )
            row = session.exec(statement).first()
            if not row:
                fallback = (
                    select(AIScoreTable)
                    .where(or_(*conditions))
                    .order_by(
                        col(AIScoreTable.version).desc(),
                        col(AIScoreTable.id).desc(),
                    )
                    .limit(1)
                )
                row = session.exec(fallback).first()

            if not row:
                # Broader fallback query on base domain
                broad_fallback = (
                    select(AIScoreTable)
                    .where(
                        or_(
                            col(AIScoreTable.account_key).like(
                                f"%{base_dom}%"
                            ),
                        )
                    )
                    .order_by(
                        col(AIScoreTable.version).desc(),
                        col(AIScoreTable.id).desc(),
                    )
                    .limit(1)
                )
                row = session.exec(broad_fallback).first()

            if not row:
                return None
            return self._format_ai_score_model(row)

    def get_score_history(
        self, conn: Any, account_key: str, version: Optional[str] = None
    ) -> List[dict]:
        base_dom = _extract_base_domain(account_key)
        target_version = version
        if not target_version and account_key.count(":") >= 2:
            parts = account_key.split(":")
            if parts[-1].startswith("v") and parts[-1][1:].isdigit():
                target_version = parts[-1]

        with _get_session(conn) as session:
            candidate_keys = [
                account_key,
                f"domain:{account_key}",
                account_key.replace("domain:", ""),
                f"domain:{base_dom}",
                base_dom,
            ]
            v_num = None
            if target_version:
                v_tag = target_version.lower()
                clean_num_str = v_tag.replace("v", "")
                v_num = int(clean_num_str) if clean_num_str.isdigit() else None
                candidate_keys.extend(
                    [
                        f"domain:{base_dom}:{v_tag}",
                        f"{base_dom}:{v_tag}",
                        f"domain:{account_key}:{v_tag}",
                        f"{account_key}:{v_tag}",
                    ]
                )
                if v_tag == "v1":
                    candidate_keys.extend(
                        [
                            f"domain:{base_dom}:v1",
                            f"{base_dom}:v1",
                        ]
                    )

            conditions: List[Any] = [
                col(AIScoreTable.account_key).in_(candidate_keys),
                col(AIScoreTable.account_key).like(f"domain:{base_dom}:v%"),
                col(AIScoreTable.account_key).like(f"{base_dom}:v%"),
            ]
            if v_num is not None:
                conditions.append(
                    and_(
                        col(AIScoreTable.account_key).in_(
                            [f"domain:{base_dom}", base_dom]
                        ),
                        AIScoreTable.version == v_num,
                    )
                )

            statement = (
                select(AIScoreTable)
                .where(or_(*conditions))
                .order_by(
                    col(AIScoreTable.version).desc(),
                    col(AIScoreTable.id).desc(),
                )
            )
            rows = session.exec(statement).all()
            if not rows:
                fallback_statement = (
                    select(AIScoreTable)
                    .where(
                        or_(
                            col(AIScoreTable.account_key).like(
                                f"%{base_dom}%"
                            ),
                        )
                    )
                    .order_by(
                        col(AIScoreTable.version).desc(),
                        col(AIScoreTable.id).desc(),
                    )
                )
                rows = session.exec(fallback_statement).all()

            return [self._format_ai_score_model(r) for r in rows]

    def get_llm_stats(self, conn: Any) -> dict:
        with _get_session(conn) as session:
            rows = session.exec(select(AIScoreTable)).all()
            if not rows:
                return {
                    "total_calls": 0,
                    "total_tokens": 0,
                    "total_cost_usd": 0.0,
                    "avg_latency_ms": 0.0,
                }
            total_calls = len(rows)
            total_cost = sum(r.cost_usd or 0.0 for r in rows)
            total_latency = sum(r.latency_ms or 0 for r in rows)
            avg_latency = total_latency / total_calls if total_calls > 0 else 0.0

            total_tokens = 0
            for r in rows:
                if r.tokens_used:
                    try:
                        t_data = (
                            json.loads(r.tokens_used)
                            if isinstance(r.tokens_used, str)
                            else r.tokens_used
                        )
                        if isinstance(t_data, dict):
                            total_tokens += (
                                t_data.get("total_tokens")
                                or t_data.get("total")
                                or (
                                    (
                                        t_data.get("prompt_tokens")
                                        or t_data.get("prompt", 0)
                                    )
                                    + (
                                        t_data.get("completion_tokens")
                                        or t_data.get("candidates", 0)
                                    )
                                )
                            )
                        elif isinstance(t_data, int):
                            total_tokens += t_data
                    except Exception:
                        pass

            return {
                "total_calls": total_calls,
                "total_tokens": total_tokens,
                "total_cost_usd": round(total_cost, 6),
                "avg_latency_ms": round(avg_latency, 2),
            }

    # =========================================================================
    # Internal / Formatting Helpers
    # =========================================================================

    def _format_ai_score_model(self, model: AIScoreTable) -> dict:
        raw_risks = getattr(model, "key_risks_json", None) or getattr(
            model, "key_risks", None
        )
        try:
            risks = (
                json.loads(raw_risks)
                if isinstance(raw_risks, str)
                else raw_risks
            )
        except Exception:
            risks = [raw_risks] if raw_risks else []

        raw_tokens = getattr(model, "tokens_used_json", None) or getattr(
            model, "tokens_used", None
        )
        try:
            tokens = (
                json.loads(raw_tokens)
                if isinstance(raw_tokens, str)
                else raw_tokens
            )
        except Exception:
            tokens = {}

        scored_time = model.scored_at
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
            "timestamp": scored_time,
            "scored_at": scored_time,
            "created_at": scored_time,
        }

