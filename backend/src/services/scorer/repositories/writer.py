import json
from datetime import datetime, timezone
from typing import Any, Union

from sqlmodel import Session, func, select

from src.services.accounts.repositories.models import AccountTable
from src.services.database import get_db_session
from src.services.scorer.repositories.models import AIScoreTable
from src.services.scorer.types import AccountScore, IScoreWriter


def _get_session(conn: Any) -> Session:
    return get_db_session(conn=conn)


class ScoreWriter(IScoreWriter):
    def save_score(self, conn: Any, score: Union[AccountScore, dict]) -> dict:
        with _get_session(conn) as session:
            acc_key = str(score["account_key"] if isinstance(score, dict) else score.account_key)
            raw_version = score.get("version") if isinstance(score, dict) else getattr(score, "version", None)
            score_val = int(score["score"] if isinstance(score, dict) else score.score)
            raw_tier = score.get("priority_tier") if isinstance(score, dict) else getattr(score, "priority_tier", None)
            tier_val = str(getattr(raw_tier, "value", raw_tier) or "tier_4_low")
            raw_risks = score.get("key_risks") if isinstance(score, dict) else getattr(score, "key_risks", [])
            risks_json = json.dumps(raw_risks) if raw_risks else "[]"
            raw_outreach = str(score.get("suggested_outreach") if isinstance(score, dict) else getattr(score, "suggested_outreach", "") or "")
            raw_rationale = str(score.get("score_rationale") if isinstance(score, dict) else getattr(score, "score_rationale", "") or "")
            raw_model_ver = str(score.get("model_version") if isinstance(score, dict) else getattr(score, "model_version", "v1.0") or "v1.0")
            raw_model_name = str(score.get("model_name") if isinstance(score, dict) else getattr(score, "model_name", "gemini-3.1-flash-lite") or "gemini-3.1-flash-lite")
            raw_tokens = score.get("tokens_used") if isinstance(score, dict) else getattr(score, "tokens_used", {})
            tokens_json = json.dumps(raw_tokens) if raw_tokens else "{}"
            if isinstance(score, dict):
                raw_lat_val = score.get("latency_ms")
                raw_cost_val = score.get("cost_usd")
                raw_time_val = score.get("timestamp") or score.get("scored_at")
            else:
                raw_lat_val = getattr(score, "latency_ms", 0)
                raw_cost_val = getattr(score, "cost_usd", 0.0)
                raw_time_val = getattr(score, "timestamp", None)

            raw_latency = int(raw_lat_val or 0)
            raw_cost = float(raw_cost_val or 0.0)
            if raw_time_val is not None and hasattr(raw_time_val, "isoformat"):
                scored_time = str(raw_time_val.isoformat())
            elif raw_time_val is not None:
                scored_time = str(raw_time_val)
            else:
                scored_time = datetime.now(timezone.utc).isoformat()

            # 1. Compute next version
            max_v_stmt = select(func.coalesce(func.max(AIScoreTable.version), 0) + 1).where(
                AIScoreTable.account_key == acc_key
            )
            calculated_v = session.exec(max_v_stmt).one()
            next_version: int = raw_version if raw_version is not None else int(calculated_v or 1)

            # 2. Mark existing records as is_latest = 0
            existing_scores = session.exec(
                select(AIScoreTable).where(AIScoreTable.account_key == acc_key, AIScoreTable.is_latest == 1)
            ).all()
            for s in existing_scores:
                s.is_latest = 0
                session.add(s)

            # 3. Insert new AI score record
            new_score = AIScoreTable(
                account_key=acc_key,
                version=next_version,
                score=score_val,
                priority_tier=tier_val,
                key_risks=risks_json,
                suggested_outreach=raw_outreach,
                score_rationale=raw_rationale,
                model_version=raw_model_ver,
                model_name=raw_model_name,
                tokens_used=tokens_json,
                latency_ms=raw_latency,
                cost_usd=raw_cost,
                scored_at=scored_time,
                is_latest=1,
            )
            session.add(new_score)

            # 4. Update accounts priority tier
            acc = session.exec(select(AccountTable).where(AccountTable.account_key == acc_key)).first()
            if acc:
                acc.priority_tier = tier_val
                session.add(acc)

            session.commit()

            return {
                "version": next_version,
                "account_key": acc_key,
                "score": score_val,
                "priority_tier": tier_val,
                "scored_at": scored_time,
            }
