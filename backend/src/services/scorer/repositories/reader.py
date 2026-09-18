import sqlite3
import json
from typing import Optional, List, Dict, Any
from src.services.scorer.types import IScoreReader


class ScoreReader(IScoreReader):

    def get_latest_score(self, conn: sqlite3.Connection, account_key: str) -> Optional[dict]:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, account_key, version, score, priority_tier, key_risks,
                   suggested_outreach, score_rationale, model_version, model_name,
                   tokens_used, latency_ms, cost_usd, scored_at
            FROM ai_scores
            WHERE (account_key = ? OR account_key = ? OR account_key = ?) AND is_latest = 1
            ORDER BY version DESC LIMIT 1
            """,
            (account_key, f"domain:{account_key}", account_key.replace("domain:", "")),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return self._format_ai_score_row(row)

    def get_score_history(self, conn: sqlite3.Connection, account_key: str) -> List[dict]:
        """Get complete chronological score version history for an account."""
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, account_key, version, score, priority_tier, key_risks,
                   suggested_outreach, score_rationale, model_version, model_name,
                   tokens_used, latency_ms, cost_usd, scored_at
            FROM ai_scores
            WHERE account_key = ? OR account_key = ? OR account_key = ?
            ORDER BY version DESC
            """,
            (account_key, f"domain:{account_key}", account_key.replace("domain:", "")),
        )
        return [self._format_ai_score_row(r) for r in cursor.fetchall()]

    def _format_ai_score_row(self, row) -> dict:
        try:
            risks = json.loads(row[5]) if isinstance(row[5], str) else row[5]
        except Exception:
            risks = [row[5]] if row[5] else []
        try:
            tokens = json.loads(row[10]) if isinstance(row[10], str) else row[10]
        except Exception:
            tokens = {}

        return {
            "id": row[0],
            "account_key": row[1],
            "version": row[2],
            "score": row[3],
            "priority_tier": row[4],
            "key_risks": risks,
            "suggested_outreach": row[6],
            "score_rationale": row[7],
            "model_version": row[8],
            "model_name": row[9],
            "tokens_used": tokens,
            "latency_ms": row[11],
            "cost_usd": row[12],
            "timestamp": row[13],
        }
