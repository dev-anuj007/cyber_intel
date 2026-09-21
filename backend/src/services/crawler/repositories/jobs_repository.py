import json
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlmodel import Session, col, func, select

from src.services.crawler.repositories.models import CrawlerJobTable
from src.services.database import get_db_session


def _get_session(conn: Any = None) -> Session:
    return get_db_session(conn=conn)


class CrawlerJobsRepository:
    def __init__(self, db_path: Optional[Any] = None, **kwargs):
        self.db_path = db_path

    def _get_conn(self, conn: Any = None):
        if conn is not None and not isinstance(conn, (str, int)):
            return conn
        return None

    def create_job(
        self,
        domain_or_conn: Any,
        scanner_type_or_job_id: Any = "standard",
        domains: Optional[List[str]] = None,
        scan_depth: str = "standard",
        enable_subdomains: bool = True,
        custom_ports: Optional[List[int]] = None,
        save_to_database: bool = True,
        user_id: Optional[int] = None,
        trace_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        if isinstance(domain_or_conn, str) and domains is None:
            domain = domain_or_conn
            scan_depth = str(scanner_type_or_job_id) if scanner_type_or_job_id else "standard"
            domains = [domain]
            job_id = f"cjob_{int(datetime.now(timezone.utc).timestamp())}_{secrets.token_hex(4)}"
            conn = None
            initial_status = "pending"
        else:
            conn = domain_or_conn
            job_id = str(scanner_type_or_job_id)
            domains = domains or kwargs.get("domains", [])
            initial_status = "queued"

        with _get_session(conn) as session:
            job = CrawlerJobTable(
                job_id=job_id,
                user_id=user_id,
                status=initial_status,
                scan_depth=scan_depth,
                enable_subdomains=1 if enable_subdomains else 0,
                custom_ports=json.dumps(custom_ports) if custom_ports else None,
                save_to_database=1 if save_to_database else 0,
                domains_input=json.dumps(domains),
                domains_count=len(domains),
                completed_count=0,
                assets_discovered_count=0,
                signals_detected_count=0,
                retry_count=0,
                max_retries=3,
                results_json="[]",
                trace_id=trace_id,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            session.add(job)
            session.commit()
            return job_id

    def get_job(self, job_id_or_conn: Any, job_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if job_id is None:
            effective_job_id = str(job_id_or_conn)
            conn = None
        else:
            effective_job_id = job_id
            conn = job_id_or_conn

        with _get_session(conn) as session:
            statement = select(CrawlerJobTable).where(CrawlerJobTable.job_id == effective_job_id)
            job = session.exec(statement).first()
            if not job:
                return None
            return self._map_job_model(job)

    def list_jobs(
        self,
        conn: Any = None,
        skip: int = 0,
        limit: int = 20,
        status: Optional[str] = None,
        **kwargs,
    ) -> Any:
        is_direct_call = False
        if conn is None or isinstance(conn, int) or isinstance(conn, str):
            is_direct_call = True
            if isinstance(conn, int):
                limit = conn
            conn = None
        if "limit" in kwargs:
            limit = kwargs["limit"]
        if "skip" in kwargs:
            skip = kwargs["skip"]

        with _get_session(conn) as session:
            query = select(CrawlerJobTable)
            count_query = select(func.count(col(CrawlerJobTable.id)))

            if status:
                query = query.where(col(CrawlerJobTable.status) == status)
                count_query = count_query.where(col(CrawlerJobTable.status) == status)

            total = session.exec(count_query).one() or 0

            query = (
                query.order_by(col(CrawlerJobTable.created_at).desc(), col(CrawlerJobTable.id).desc())
                .offset(skip)
                .limit(limit)
            )
            rows = session.exec(query).all()
            items = [self._map_job_model(r) for r in rows]
            if is_direct_call:
                return items
            return items, total

    def start_job(self, conn: Any, job_id: str) -> None:
        with _get_session(conn) as session:
            job = session.exec(select(CrawlerJobTable).where(CrawlerJobTable.job_id == job_id)).first()
            if job:
                job.status = "running"
                if not job.started_at:
                    job.started_at = datetime.now(timezone.utc).isoformat()
                session.add(job)
                session.commit()

    def update_job_status(self, job_id: str, status: str, progress: int = 0, conn: Any = None) -> None:
        with _get_session(conn) as session:
            job = session.exec(select(CrawlerJobTable).where(CrawlerJobTable.job_id == job_id)).first()
            if job:
                job.status = status
                if progress is not None and progress > 0:
                    job.completed_count = progress
                session.add(job)
                session.commit()

    def update_job_progress(
        self,
        conn: Any,
        job_id: str,
        completed_count: int,
        assets_count: int,
        signals_count: int,
        results: List[Dict[str, Any]],
    ) -> None:
        with _get_session(conn) as session:
            job = session.exec(select(CrawlerJobTable).where(CrawlerJobTable.job_id == job_id)).first()
            if job:
                job.completed_count = completed_count
                job.assets_discovered_count = assets_count
                job.signals_detected_count = signals_count
                job.results_json = json.dumps(results)
                session.add(job)
                session.commit()

    def complete_job(
        self,
        job_id_or_conn: Any,
        results_or_summary: Any = None,
        assets_count: int = 0,
        signals_count: int = 0,
        **kwargs,
    ) -> None:
        if isinstance(job_id_or_conn, str):
            effective_job_id = job_id_or_conn
            conn = None
            summary = results_or_summary if isinstance(results_or_summary, dict) else kwargs.get("results_summary", {})
            results = kwargs.get("results", [])
            assets_cnt = summary.get("assets", assets_count) if summary else assets_count
            signals_cnt = summary.get("signals", signals_count) if summary else signals_count
        else:
            conn = job_id_or_conn
            effective_job_id = kwargs.get("job_id", "")
            results = results_or_summary
            assets_cnt = assets_count
            signals_cnt = signals_count

        with _get_session(conn) as session:
            job = session.exec(select(CrawlerJobTable).where(CrawlerJobTable.job_id == effective_job_id)).first()
            if job:
                job.status = "completed"
                job.completed_count = job.domains_count
                job.assets_discovered_count = assets_cnt
                job.signals_detected_count = signals_cnt
                if results:
                    job.results_json = json.dumps(results)
                job.completed_at = datetime.now(timezone.utc).isoformat()
                session.add(job)
                session.commit()

    def fail_job(
        self,
        job_id_or_conn: Any,
        error_message: str = "Unknown error",
        conn: Optional[Any] = None,
    ) -> None:
        if isinstance(job_id_or_conn, str):
            effective_job_id = job_id_or_conn
            effective_conn = conn
        else:
            effective_job_id = str(error_message)
            error_message = str(conn or "Unknown error")
            effective_conn = job_id_or_conn

        with _get_session(effective_conn) as session:
            job = session.exec(select(CrawlerJobTable).where(CrawlerJobTable.job_id == effective_job_id)).first()
            if job:
                job.status = "failed"
                job.error_message = error_message
                job.completed_at = datetime.now(timezone.utc).isoformat()
                session.add(job)
                session.commit()

    def increment_retry(self, conn: Any, job_id: str) -> int:
        with _get_session(conn) as session:
            job = session.exec(select(CrawlerJobTable).where(CrawlerJobTable.job_id == job_id)).first()
            if job:
                job.retry_count = (job.retry_count or 0) + 1
                job.status = "queued"
                job.error_message = None
                session.add(job)
                session.commit()
                return job.retry_count
            return 0

    def recover_stale_jobs(self, conn: Any) -> int:
        with _get_session(conn) as session:
            stale_jobs = session.exec(select(CrawlerJobTable).where(CrawlerJobTable.status == "running")).all()
            for job in stale_jobs:
                job.status = "queued"
            session.commit()
            return len(stale_jobs)

    def _map_job_model(self, job: CrawlerJobTable) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "id": job.id,
            "job_id": job.job_id,
            "user_id": job.user_id,
            "status": "pending" if job.status == "queued" else job.status,
            "scan_depth": job.scan_depth,
            "enable_subdomains": bool(job.enable_subdomains),
            "custom_ports": job.custom_ports,
            "save_to_database": bool(job.save_to_database),
            "domains_input": job.domains_input,
            "domains_count": job.domains_count,
            "completed_count": job.completed_count,
            "assets_discovered_count": job.assets_discovered_count,
            "signals_detected_count": job.signals_detected_count,
            "retry_count": job.retry_count,
            "max_retries": job.max_retries,
            "results_json": job.results_json,
            "error_message": job.error_message,
            "trace_id": job.trace_id,
            "created_at": str(job.created_at) if job.created_at else None,
            "started_at": str(job.started_at) if job.started_at else None,
            "completed_at": str(job.completed_at) if job.completed_at else None,
        }

        try:
            d["domains"] = json.loads(job.domains_input or "[]")
        except Exception:
            d["domains"] = []

        try:
            d["results"] = json.loads(job.results_json or "[]")
        except Exception:
            d["results"] = []

        if isinstance(job.custom_ports, str):
            try:
                d["custom_ports"] = json.loads(job.custom_ports)
            except Exception:
                d["custom_ports"] = None

        d["domain"] = d["domains"][0] if d.get("domains") else "unknown"
        d["domains_preview"] = d["domains"][:5]

        if d.get("status") == "completed":
            d["progress"] = 100
        elif d.get("domains_count", 0) > 1 and d.get("completed_count", 0) <= d.get("domains_count", 1):
            d["progress"] = int((d.get("completed_count", 0) / max(1, d.get("domains_count", 1))) * 100)
        else:
            d["progress"] = d.get("completed_count", 0)

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
