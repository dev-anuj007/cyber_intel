import time
from typing import Optional, List, Dict, Any
from src.services.scorer.types import AccountScore, IScoreReader, IScoreWriter
from src.services.database import get_dynamo_resource, get_table_name, float_to_decimal, decimal_to_python
from src.services.logger import get_logger

logger = get_logger("services.scorer.dynamo")


class DynamoScoreRepository(IScoreReader, IScoreWriter):

    def __init__(self, table_name: Optional[str] = None):
        self._table_name = table_name or get_table_name("scores")
        self._table = None

    @property
    def table(self):
        if self._table is None:
            dynamo = get_dynamo_resource()
            self._table = dynamo.Table(self._table_name)
        return self._table

    def save_score(self, conn: Any, score: AccountScore) -> dict:
        """Save an AI score to DynamoDB with versioning."""
        try:
            acc_key = score.account_key
            scored_time = score.timestamp.isoformat() if hasattr(score.timestamp, "isoformat") else str(score.timestamp)
            tier_val = score.priority_tier.value if hasattr(score.priority_tier, "value") else str(score.priority_tier)

            history = self.get_score_history(conn, acc_key)
            next_version = len(history) + 1

            item = {
                "account_key": acc_key,
                "created_at": scored_time,
                "version": next_version,
                "score": score.score,
                "priority_tier": tier_val,
                "key_risks": score.key_risks or [],
                "suggested_outreach": score.suggested_outreach or "",
                "score_rationale": score.score_rationale or "",
                "model_version": score.model_version or "",
                "tokens_used": score.tokens_used or {},
                "latency_ms": score.latency_ms or 0.0,
                "cost_usd": score.cost_usd or 0.0,
                "is_latest": True,
            }

            self.table.put_item(Item=float_to_decimal(item))
            logger.info("Saved AI score in DynamoDB", account_key=acc_key, version=next_version, score=score.score)

            return {
                "version": next_version,
                "account_key": acc_key,
                "score": score.score,
                "priority_tier": tier_val,
                "scored_at": scored_time,
                "model_version": score.model_version,
            }
        except Exception as e:
            logger.error(f"Error saving AI score to DynamoDB: {e}", account_key=score.account_key)
            return {
                "version": 1,
                "account_key": score.account_key,
                "score": score.score,
                "priority_tier": str(score.priority_tier),
                "scored_at": str(score.timestamp),
            }

    def get_latest_score(self, conn: Any, account_key: str) -> Optional[dict]:
        """Fetch the most recent AI score for an account."""
        history = self.get_score_history(conn, account_key)
        if history:
            return history[0]
        return None

    def get_score_history(self, conn: Any, account_key: str) -> List[dict]:
        """Fetch all historical score records for an account sorted descending."""
        try:
            keys_to_try = [
                account_key,
                f"domain:{account_key}",
                account_key.replace("domain:", "")
            ]
            all_items = []
            for k in set(keys_to_try):
                resp = self.table.query(
                    KeyConditionExpression="account_key = :ak",
                    ExpressionAttributeValues={":ak": k},
                    ScanIndexForward=False,
                )
                items = resp.get("Items", [])
                if items:
                    all_items.extend(items)

            if not all_items:
                return []

            parsed = [decimal_to_python(it) for it in all_items]
            parsed.sort(key=lambda x: (x.get("version", 0), x.get("created_at", "")), reverse=True)

            formatted = []
            for it in parsed:
                formatted.append({
                    "id": f"{it.get('account_key')}_{it.get('version')}",
                    "account_key": it.get("account_key"),
                    "version": it.get("version", 1),
                    "score": it.get("score"),
                    "priority_tier": it.get("priority_tier"),
                    "key_risks": it.get("key_risks", []),
                    "suggested_outreach": it.get("suggested_outreach", ""),
                    "score_rationale": it.get("score_rationale", ""),
                    "model_version": it.get("model_version", ""),
                    "model_name": it.get("model_version", ""),
                    "tokens_used": it.get("tokens_used", {}),
                    "latency_ms": it.get("latency_ms", 0),
                    "cost_usd": it.get("cost_usd", 0.0),
                    "scored_at": it.get("created_at", ""),
                })
            return formatted
        except Exception as e:
            logger.error(f"Error querying score history from DynamoDB: {e}", account_key=account_key)
            return []
