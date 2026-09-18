from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

from src.services.database import (
    get_dynamo_resource,
    get_table_name,
    float_to_decimal,
    decimal_to_python,
)
from src.services.jobs.types import IJobsRepository
from src.services.logger import get_logger

logger = get_logger("services.jobs.dynamo")


class DynamoJobsRepository(IJobsRepository):

    def __init__(self, table_name: Optional[str] = None):
        self._table_name = table_name or get_table_name("jobs")
        self._table = None

    @property
    def table(self):
        if self._table is None:
            dynamo = get_dynamo_resource()
            self._table = dynamo.Table(self._table_name)
        return self._table

    def create_job(
        self,
        conn: Any,
        job_id: str,
        job_type: str,
        title: str,
        payload: Dict[str, Any],
        progress_total: int = 1,
        user_id: Optional[Any] = None,
        max_retries: int = 3,
        trace_id: Optional[str] = None,
    ) -> str:
        now_str = datetime.now(timezone.utc).isoformat()
        item = {
            "job_id": job_id,
            "job_type": job_type,
            "title": title,
            "user_id": str(user_id) if user_id is not None else None,
            "status": "queued",
            "progress_current": 0,
            "progress_total": progress_total,
            "retry_count": 0,
            "max_retries": max_retries,
            "payload": payload or {},
            "results": None,
            "metadata": {},
            "error_message": None,
            "trace_id": trace_id,
            "created_at": now_str,
            "started_at": None,
            "completed_at": None,
        }
        self.table.put_item(Item=float_to_decimal(item))
        logger.info("Created background job in DynamoDB", job_id=job_id, job_type=job_type)
        return job_id

    def get_job(self, conn: Any, job_id: str) -> Optional[Dict[str, Any]]:
        try:
            resp = self.table.get_item(Key={"job_id": job_id})
            item = resp.get("Item")
            if not item:
                return None
            return self._map_item(decimal_to_python(item))
        except Exception as e:
            logger.error(f"Error getting job from DynamoDB: {e}", job_id=job_id)
            return None

    def list_jobs(
        self,
        conn: Any,
        skip: int = 0,
        limit: int = 20,
        job_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        try:
            filter_exp = None
            expr_vals = {}

            if job_type and status:
                filter_exp = "job_type = :jt AND #st = :st"
                expr_vals = {":jt": job_type, ":st": status}
            elif job_type:
                filter_exp = "job_type = :jt"
                expr_vals = {":jt": job_type}
            elif status:
                filter_exp = "#st = :st"
                expr_vals = {":st": status}

            kwargs = {}
            if filter_exp:
                kwargs["FilterExpression"] = filter_exp
                kwargs["ExpressionAttributeValues"] = expr_vals
                if status:
                    kwargs["ExpressionAttributeNames"] = {"#st": "status"}

            resp = self.table.scan(**kwargs)
            items = resp.get("Items", [])
            total = len(items)

            parsed = [self._map_item(decimal_to_python(it)) for it in items]
            parsed.sort(key=lambda x: x.get("created_at", ""), reverse=True)

            paginated = parsed[skip : skip + limit]
            return paginated, total
        except Exception as e:
            logger.error(f"Error listing jobs from DynamoDB: {e}")
            return [], 0

    def start_job(self, conn: Any, job_id: str) -> None:
        try:
            now_str = datetime.now(timezone.utc).isoformat()
            self.table.update_item(
                Key={"job_id": job_id},
                UpdateExpression="SET #st = :st, started_at = if_not_exists(started_at, :sa)",
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={":st": "running", ":sa": now_str},
            )
        except Exception as e:
            logger.error(f"Error starting job in DynamoDB: {e}", job_id=job_id)

    def update_progress(
        self,
        conn: Any,
        job_id: str,
        current: int,
        total: int,
        metadata: Optional[Dict[str, Any]] = None,
        partial_results: Optional[Any] = None,
    ) -> None:
        try:
            update_parts = ["progress_current = :pc", "progress_total = :pt"]
            expr_vals = {":pc": current, ":pt": total}

            if metadata is not None:
                update_parts.append("#md = :md")
                expr_vals[":md"] = float_to_decimal(metadata)
            if partial_results is not None:
                update_parts.append("results = :res")
                expr_vals[":res"] = float_to_decimal(partial_results)

            kwargs = {
                "Key": {"job_id": job_id},
                "UpdateExpression": f"SET {', '.join(update_parts)}",
                "ExpressionAttributeValues": expr_vals,
            }
            if metadata is not None:
                kwargs["ExpressionAttributeNames"] = {"#md": "metadata"}

            self.table.update_item(**kwargs)
        except Exception as e:
            logger.error(f"Error updating job progress in DynamoDB: {e}", job_id=job_id)

    def complete_job(
        self,
        conn: Any,
        job_id: str,
        results: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        try:
            now_str = datetime.now(timezone.utc).isoformat()
            update_parts = [
                "#st = :st",
                "progress_current = progress_total",
                "results = :res",
                "completed_at = :ca",
            ]
            expr_vals = {
                ":st": "completed",
                ":res": float_to_decimal(results),
                ":ca": now_str,
            }
            expr_names = {"#st": "status"}

            if metadata is not None:
                update_parts.append("#md = :md")
                expr_vals[":md"] = float_to_decimal(metadata)
                expr_names["#md"] = "metadata"

            self.table.update_item(
                Key={"job_id": job_id},
                UpdateExpression=f"SET {', '.join(update_parts)}",
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_vals,
            )
            logger.info("Completed job in DynamoDB", job_id=job_id)
        except Exception as e:
            logger.error(f"Error completing job in DynamoDB: {e}", job_id=job_id)

    def fail_job(self, conn: Any, job_id: str, error_message: str) -> None:
        try:
            now_str = datetime.now(timezone.utc).isoformat()
            self.table.update_item(
                Key={"job_id": job_id},
                UpdateExpression="SET #st = :st, error_message = :em, completed_at = :ca",
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={
                    ":st": "failed",
                    ":em": error_message,
                    ":ca": now_str,
                },
            )
        except Exception as e:
            logger.error(f"Error failing job in DynamoDB: {e}", job_id=job_id)

    def increment_retry(self, conn: Any, job_id: str) -> int:
        try:
            resp = self.table.update_item(
                Key={"job_id": job_id},
                UpdateExpression="SET retry_count = retry_count + :one, #st = :st REMOVE error_message",
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={":one": 1, ":st": "queued"},
                ReturnValues="UPDATED_NEW",
            )
            return int(resp.get("Attributes", {}).get("retry_count", 0))
        except Exception as e:
            logger.error(f"Error incrementing job retry in DynamoDB: {e}", job_id=job_id)
            return 0

    def recover_stale_jobs(self, conn: Any) -> int:
        return 0

    def _map_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        current = int(item.get("progress_current", 0) or 0)
        total = max(1, int(item.get("progress_total", 1) or 1))
        status = item.get("status", "queued")
        progress_percent = min(100, int((current / total) * 100)) if status != "completed" else 100

        duration_ms = None
        if item.get("started_at") and item.get("completed_at"):
            try:
                t0 = datetime.fromisoformat(str(item["started_at"]).replace("Z", "+00:00"))
                t1 = datetime.fromisoformat(str(item["completed_at"]).replace("Z", "+00:00"))
                duration_ms = int((t1 - t0).total_seconds() * 1000)
            except Exception:
                pass

        user_id = item.get("user_id")
        if user_id is not None and str(user_id).isdigit():
            user_id = int(user_id)

        return {
            "id": item.get("job_id"),
            "job_id": item.get("job_id"),
            "job_type": item.get("job_type"),
            "title": item.get("title"),
            "user_id": user_id,
            "status": status,
            "progress_current": current,
            "progress_total": total,
            "progress_percent": progress_percent,
            "retry_count": int(item.get("retry_count", 0) or 0),
            "max_retries": int(item.get("max_retries", 3) or 3),
            "payload": item.get("payload", {}),
            "results": item.get("results"),
            "metadata": item.get("metadata", {}),
            "error_message": item.get("error_message"),
            "trace_id": item.get("trace_id"),
            "created_at": item.get("created_at"),
            "started_at": item.get("started_at"),
            "completed_at": item.get("completed_at"),
            "duration_ms": duration_ms,
        }
