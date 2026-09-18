import sqlite3
import json
from src.services.scorer.types import IScoreWriter, AccountScore


class ScoreWriter(IScoreWriter):

    def save_score(self, conn: sqlite3.Connection, score: AccountScore) -> dict:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM ai_scores WHERE account_key = ?",
            (score.account_key,),
        )
        next_version = cursor.fetchone()[0]

        cursor.execute("UPDATE ai_scores SET is_latest = 0 WHERE account_key = ?", (score.account_key,))

        tier_val = score.priority_tier.value if hasattr(score.priority_tier, "value") else str(score.priority_tier)
        tokens_json = json.dumps(score.tokens_used) if score.tokens_used else "{}"
        risks_json = json.dumps(score.key_risks) if score.key_risks else "[]"
        scored_time = score.timestamp.isoformat() if hasattr(score.timestamp, "isoformat") else str(score.timestamp)

        cursor.execute(
            """
            INSERT INTO ai_scores (
                account_key, version, score, priority_tier, key_risks,
                suggested_outreach, score_rationale, model_version, tokens_used,
                latency_ms, cost_usd, scored_at, is_latest
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                score.account_key,
                next_version,
                score.score,
                tier_val,
                risks_json,
                score.suggested_outreach,
                score.score_rationale,
                score.model_version,
                tokens_json,
                score.latency_ms,
                score.cost_usd,
                scored_time,
            ),
        )

        cursor.execute("UPDATE accounts SET priority_tier = ? WHERE account_key = ?", (tier_val, score.account_key))

        return {
            "version": next_version,
            "account_key": score.account_key,
            "score": score.score,
            "priority_tier": tier_val,
            "scored_at": scored_time,
        }
