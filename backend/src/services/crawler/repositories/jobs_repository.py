import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple


class CrawlerJobsRepository:
    def create_job(
        self,
        conn,
        job_id: str,
        domains: List[str],
        scan_depth: str = "standard",
        enable_subdomains: bool = True,
        custom_ports: Optional[List[int]] = None,
        save_to_database: bool = True,
        user_id: Optional[int] = None,
        trace_id: Optional[str] = None,
    ) -> str:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO crawler_jobs (
                job_id,
                user_id,
                status,
                scan_depth,
                enable_subdomains,
                custom_ports,
                save_to_database,
                domains_input,
                domains_count,
                completed_count,
                assets_discovered_count,
                signals_detected_count,
                retry_count,
                max_retries,
                results_json,
                trace_id,
                created_at
            ) VALUES (?, ?, 'queued', ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 3, '[]', ?, CURRENT_TIMESTAMP)
            """,
            (
                job_id,
                user_id,
                scan_depth,
                1 if enable_subdomains else 0,
                json.dumps(custom_ports) if custom_ports else None,
                1 if save_to_database else 0,
                json.dumps(domains),
                len(domains),
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
                user_id,
                status,
                scan_depth,
                enable_subdomains,
                custom_ports,
                save_to_database,
                domains_input,
                domains_count,
                completed_count,
                assets_discovered_count,
                signals_detected_count,
                retry_count,
                max_retries,
                results_json,
                error_message,
                trace_id,
                created_at,
                started_at,
                completed_at
            FROM crawler_jobs
            WHERE job_id = ?
            """,
            (job_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        return self._map_job_row(row)

    def list_jobs(
        self,
        conn,
        skip: int = 0,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        cursor = conn.cursor()
        if status:
            cursor.execute("SELECT COUNT(*) FROM crawler_jobs WHERE status = ?", (status,))
            total = cursor.fetchone()[0]
            cursor.execute(
                """
                SELECT
                    id,
                    job_id,
                    user_id,
                    status,
                    scan_depth,
                    enable_subdomains,
                    custom_ports,
                    save_to_database,
                    domains_input,
                    domains_count,
                    completed_count,
                    assets_discovered_count,
                    signals_detected_count,
                    retry_count,
                    max_retries,
                    results_json,
                    error_message,
                    trace_id,
                    created_at,
                    started_at,
                    completed_at
                FROM crawler_jobs
                WHERE status = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (status, limit, skip),
            )
        else:
            cursor.execute("SELECT COUNT(*) FROM crawler_jobs")
            total = cursor.fetchone()[0]
            cursor.execute(
                """
                SELECT
                    id,
                    job_id,
                    user_id,
                    status,
                    scan_depth,
                    enable_subdomains,
                    custom_ports,
                    save_to_database,
                    domains_input,
                    domains_count,
                    completed_count,
                    assets_discovered_count,
                    signals_detected_count,
                    retry_count,
                    max_retries,
                    results_json,
                    error_message,
                    trace_id,
                    created_at,
                    started_at,
                    completed_at
                FROM crawler_jobs
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (limit, skip),
            )

        rows = cursor.fetchall()
        items = [self._map_job_row(r) for r in rows]
        return items, total

    def start_job(self, conn, job_id: str) -> None:
        cursor = conn.cursor()
        now_str = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            """
            UPDATE crawler_jobs
            SET status = 'running', started_at = COALESCE(started_at, ?)
            WHERE job_id = ?
            """,
            (now_str, job_id),
        )

    def update_job_progress(
        self,
        conn,
        job_id: str,
        completed_count: int,
        assets_count: int,
        signals_count: int,
        results: List[Dict[str, Any]],
    ) -> None:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE crawler_jobs
            SET
                completed_count = ?,
                assets_discovered_count = ?,
                signals_detected_count = ?,
                results_json = ?
            WHERE job_id = ?
            """,
            (
                completed_count,
                assets_count,
                signals_count,
                json.dumps(results),
                job_id,
            ),
        )

    def complete_job(
        self,
        conn,
        job_id: str,
        results: List[Dict[str, Any]],
        assets_count: int,
        signals_count: int,
    ) -> None:
        cursor = conn.cursor()
        now_str = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            """
            UPDATE crawler_jobs
            SET
                status = 'completed',
                completed_count = domains_count,
                assets_discovered_count = ?,
                signals_detected_count = ?,
                results_json = ?,
                completed_at = ?
            WHERE job_id = ?
            """,
            (
                assets_count,
                signals_count,
                json.dumps(results),
                now_str,
                job_id,
            ),
        )

    def fail_job(self, conn, job_id: str, error_message: str) -> None:
        cursor = conn.cursor()
        now_str = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            """
            UPDATE crawler_jobs
            SET status = 'failed', error_message = ?, completed_at = ?
            WHERE job_id = ?
            """,
            (error_message, now_str, job_id),
        )

    def increment_retry(self, conn, job_id: str) -> int:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE crawler_jobs
            SET retry_count = retry_count + 1, status = 'queued', error_message = NULL
            WHERE job_id = ?
            """,
            (job_id,),
        )
        cursor.execute("SELECT retry_count FROM crawler_jobs WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        return row[0] if row else 0

    def recover_stale_jobs(self, conn) -> int:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE crawler_jobs
            SET status = 'queued'
            WHERE status = 'running'
            """
        )
        return cursor.rowcount

    def _map_job_row(self, row) -> Dict[str, Any]:
        if hasattr(row, "keys"):
            d = dict(row)
        else:
            d = {
                "id": row[0],
                "job_id": row[1],
                "user_id": row[2],
                "status": row[3],
                "scan_depth": row[4],
                "enable_subdomains": bool(row[5]),
                "custom_ports": row[6],
                "save_to_database": bool(row[7]),
                "domains_input": row[8],
                "domains_count": row[9],
                "completed_count": row[10],
                "assets_discovered_count": row[11],
                "signals_detected_count": row[12],
                "retry_count": row[13],
                "max_retries": row[14],
                "results_json": row[15],
                "error_message": row[16],
                "trace_id": row[17],
                "created_at": row[18],
                "started_at": row[19],
                "completed_at": row[20],
            }

        try:
            d["domains"] = json.loads(d.get("domains_input") or "[]")
        except Exception:
            d["domains"] = []

        try:
            d["results"] = json.loads(d.get("results_json") or "[]")
        except Exception:
            d["results"] = []

        if isinstance(d.get("custom_ports"), str):
            try:
                d["custom_ports"] = json.loads(d["custom_ports"])
            except Exception:
                d["custom_ports"] = None

        d["domains_preview"] = d["domains"][:5]

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
