import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple


class JobsRepository:
    def create_job(
        self,
        conn,
        job_id: str,
        job_type: str,
        title: str,
        payload: Dict[str, Any],
        progress_total: int = 1,
        user_id: Optional[int] = None,
        max_retries: int = 3,
        trace_id: Optional[str] = None,
    ) -> str:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO background_jobs (
                job_id,
                job_type,
                title,
                user_id,
                status,
                progress_current,
                progress_total,
                retry_count,
                max_retries,
                payload_json,
                results_json,
                metadata_json,
                trace_id,
                created_at
            ) VALUES (?, ?, ?, ?, 'queued', 0, ?, 0, ?, ?, 'null', '{}', ?, CURRENT_TIMESTAMP)
            """,
            (
                job_id,
                job_type,
                title,
                user_id,
                progress_total,
                max_retries,
                json.dumps(payload),
                trace_id,
            ),
        )
        return job_id

    def get_job(self, conn, job_id: str) -> Optional[Dict[str, Any]]:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                id,
                job_id,
                job_type,
                title,
                user_id,
                status,
                progress_current,
                progress_total,
                retry_count,
                max_retries,
                payload_json,
                results_json,
                metadata_json,
                error_message,
                trace_id,
                created_at,
                started_at,
                completed_at
            FROM background_jobs
            WHERE job_id = ?
            """,
            (job_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        return self._map_row(row)

    def list_jobs(
        self,
        conn,
        skip: int = 0,
        limit: int = 20,
        job_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        cursor = conn.cursor()
        where_clauses = []
        params: List[Any] = []

        if job_type:
            where_clauses.append("job_type = ?")
            params.append(job_type)
        if status:
            where_clauses.append("status = ?")
            params.append(status)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        cursor.execute(f"SELECT COUNT(*) FROM background_jobs {where_sql}", tuple(params))
        total = cursor.fetchone()[0]

        query = f"""
            SELECT
                id,
                job_id,
                job_type,
                title,
                user_id,
                status,
                progress_current,
                progress_total,
                retry_count,
                max_retries,
                payload_json,
                results_json,
                metadata_json,
                error_message,
                trace_id,
                created_at,
                started_at,
                completed_at
            FROM background_jobs
            {where_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
        """
        exec_params = list(params) + [limit, skip]
        cursor.execute(query, tuple(exec_params))
        rows = cursor.fetchall()
        items = [self._map_row(r) for r in rows]
        return items, total

    def start_job(self, conn, job_id: str) -> None:
        cursor = conn.cursor()
        now_str = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            """
            UPDATE background_jobs
            SET status = 'running', started_at = COALESCE(started_at, ?)
            WHERE job_id = ?
            """,
            (now_str, job_id),
        )

    def update_progress(
        self,
        conn,
        job_id: str,
        current: int,
        total: int,
        metadata: Optional[Dict[str, Any]] = None,
        partial_results: Optional[Any] = None,
    ) -> None:
        cursor = conn.cursor()
        sql_parts = ["progress_current = ?", "progress_total = ?"]
        params = [current, total]

        if metadata is not None:
            sql_parts.append("metadata_json = ?")
            params.append(json.dumps(metadata))

        if partial_results is not None:
            sql_parts.append("results_json = ?")
            params.append(json.dumps(partial_results))

        params.append(job_id)
        cursor.execute(
            f"UPDATE background_jobs SET {', '.join(sql_parts)} WHERE job_id = ?",
            tuple(params),
        )

    def complete_job(
        self,
        conn,
        job_id: str,
        results: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        cursor = conn.cursor()
        now_str = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            """
            UPDATE background_jobs
            SET
                status = 'completed',
                progress_current = progress_total,
                results_json = ?,
                metadata_json = COALESCE(?, metadata_json),
                completed_at = ?
            WHERE job_id = ?
            """,
            (
                json.dumps(results),
                json.dumps(metadata) if metadata is not None else None,
                now_str,
                job_id,
            ),
        )

    def fail_job(self, conn, job_id: str, error_message: str) -> None:
        cursor = conn.cursor()
        now_str = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            """
            UPDATE background_jobs
            SET status = 'failed', error_message = ?, completed_at = ?
            WHERE job_id = ?
            """,
            (error_message, now_str, job_id),
        )

    def increment_retry(self, conn, job_id: str) -> int:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE background_jobs
            SET retry_count = retry_count + 1, status = 'queued', error_message = NULL
            WHERE job_id = ?
            """,
            (job_id,),
        )
        cursor.execute("SELECT retry_count FROM background_jobs WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        return row[0] if row else 0

    def recover_stale_jobs(self, conn) -> int:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE background_jobs
            SET status = 'queued'
            WHERE status = 'running'
            """
        )
        return cursor.rowcount

    def _map_row(self, row) -> Dict[str, Any]:
        if hasattr(row, "keys"):
            d = dict(row)
        else:
            d = {
                "id": row[0],
                "job_id": row[1],
                "job_type": row[2],
                "title": row[3],
                "user_id": row[4],
                "status": row[5],
                "progress_current": row[6],
                "progress_total": row[7],
                "retry_count": row[8],
                "max_retries": row[9],
                "payload_json": row[10],
                "results_json": row[11],
                "metadata_json": row[12],
                "error_message": row[13],
                "trace_id": row[14],
                "created_at": row[15],
                "started_at": row[16],
                "completed_at": row[17],
            }

        try:
            d["payload"] = json.loads(d.get("payload_json") or "{}")
        except Exception:
            d["payload"] = {}

        try:
            d["results"] = json.loads(d.get("results_json") or "null")
        except Exception:
            d["results"] = None

        try:
            d["metadata"] = json.loads(d.get("metadata_json") or "{}")
        except Exception:
            d["metadata"] = {}

        current = d.get("progress_current", 0)
        total = max(1, d.get("progress_total", 1))
        d["progress_percent"] = min(100, int((current / total) * 100)) if d.get("status") != "completed" else 100

        duration_ms = None
        if d.get("started_at") and d.get("completed_at"):
            try:
                t0 = datetime.fromisoformat(str(d["started_at"]).replace("Z", "+00:00"))
                t1 = datetime.fromisoformat(str(d["completed_at"]).replace("Z", "+00:00"))
                duration_ms = int((t1 - t0).total_seconds() * 1000)
            except Exception:
                pass
        d["duration_ms"] = duration_ms

        return d
