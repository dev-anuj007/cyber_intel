import json
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, func, select

from src.services.accounts.internals.repositories.models.account import AccountTable
from src.services.database.dependencies import get_db_session
from src.services.scorer.internals.repositories.models import AIScoreTable
from src.services.scorer.protocols import IScoreWriter
from src.services.scorer.types import AccountScore


def _get_session(conn: Any) -> Session:
    return get_db_session(conn=conn)


class ScoreWriter(IScoreWriter):
    def save_score(self, conn: Any, score: AccountScore) -> dict:
        with _get_session(conn) as session:
            acc_key = score.account_key
            score_val = score.score
            tier_val = (
                score.priority_tier.value
                if hasattr(score.priority_tier, "value")
                else str(score.priority_tier)
            )
            risks_json = json.dumps(score.key_risks or [])
            outreach = score.suggested_outreach or ""
            rationale = score.score_rationale or score.reasoning or ""
            model_ver = score.model_version or score.prompt_version or "v1.0"
            model_name = score.model_name or score.model or "gemini-2.5-flash"
            tokens_json = json.dumps(
                score.tokens_used
                or {
                    "input": score.input_tokens or 0,
                    "output": score.output_tokens or 0,
                    "total": score.total_tokens or 0,
                }
            )
            latency = score.latency_ms or score.scoring_time_ms or 0
            cost = score.cost_usd or 0.0
            scored_time = (
                score.calculated_at.isoformat()
                if score.calculated_at
                else datetime.now(timezone.utc).isoformat()
            )

            if score.version is not None:
                next_version = score.version
            else:
                max_v_stmt = select(
                    func.coalesce(func.max(AIScoreTable.version), 0) + 1
                ).where(AIScoreTable.account_key == acc_key)
                next_version = int(session.exec(max_v_stmt).one() or 1)

            existing_scores = session.exec(
                select(AIScoreTable).where(
                    AIScoreTable.account_key == acc_key,
                    AIScoreTable.is_latest == 1,
                )
            ).all()
            for s in existing_scores:
                s.is_latest = 0
                session.add(s)

            new_score = AIScoreTable(
                account_key=acc_key,
                version=next_version,
                score=score_val,
                priority_tier=tier_val,
                key_risks=risks_json,
                suggested_outreach=outreach,
                score_rationale=rationale,
                model_version=model_ver,
                model_name=model_name,
                tokens_used=tokens_json,
                latency_ms=latency,
                cost_usd=cost,
                scored_at=scored_time,
                is_latest=1,
            )

            session.add(new_score)

            acc = session.exec(
                select(AccountTable).where(AccountTable.account_key == acc_key)
            ).first()
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
