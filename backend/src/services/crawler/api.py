from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends

from src.core.exceptions import InvalidInputError, NotFoundError
from src.services.crawler.types import (
    CrawlerRunRequest,
    CrawlerJobSubmitRequest,
)
from src.services.jobs.types import (
    JobSubmitResponse,
    JobSummary,
    JobDetail,
    JobListResponse,
    JobStatus,
)
from src.services.crawler.crawler_service import CrawlerService, default_crawler_service
from src.services.accounts.accounts_service import AccountsService, default_accounts_service
from src.services.jobs.jobs_service import JobsService, default_jobs_service
from src.services.auth.api import get_current_user_optional
from src.services.logger import get_logger

logger = get_logger("crawler.api")

router = APIRouter(prefix="/api/crawler", tags=["Domain Crawler"])


def get_crawler_service() -> CrawlerService:
    return default_crawler_service


def get_accounts_service() -> AccountsService:
    return default_accounts_service


def get_jobs_service() -> JobsService:
    return default_jobs_service


@router.post("/jobs", response_model=JobSubmitResponse, status_code=202)
def submit_crawler_job(
    req: CrawlerJobSubmitRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    crawler: CrawlerService = Depends(get_crawler_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
    jobs_service: JobsService = Depends(get_jobs_service),
):
    """Submit an asynchronous domain perimeter scan job to run in the background."""
    crawler.set_accounts_service(accounts_service)

    clean_domains = [d.strip().replace("https://", "").replace("http://", "").rstrip("/") for d in req.domains if d.strip()]
    if not clean_domains:
        raise InvalidInputError("At least one target domain is required", code="MISSING_TARGET_DOMAINS")

    user_id = current_user.get("id") if current_user else None

    if req.pipeline_name and req.pipeline_name.strip():
        title = req.pipeline_name.strip()
    elif len(clean_domains) == 1:
        title = f"{clean_domains[0]} Recon"
    elif len(clean_domains) <= 3:
        title = f"{', '.join(clean_domains)} Recon"
    else:
        title = f"{clean_domains[0]}, {clean_domains[1]} (+{len(clean_domains)-2} more)"

    payload = {
        "pipeline_name": req.pipeline_name.strip() if req.pipeline_name else None,
        "domains": clean_domains,
        "scan_depth": req.scan_depth,
        "scanner_type": req.scanner_type or "all",
        "enable_subdomains": req.enable_subdomains,
        "custom_ports": req.custom_ports,
        "save_to_database": req.save_to_database,
    }

    job_id = jobs_service.submit_job(
        job_type="crawler_scan",
        title=title,
        payload=payload,
        progress_total=len(clean_domains),
        user_id=user_id,
        max_retries=3,
        auto_start=True,
    )

    return JobSubmitResponse(
        success=True,
        job_id=job_id,
        job_type="crawler_scan",
        status=JobStatus.QUEUED,
        message=f"Perimeter scan queued for {len(clean_domains)} domains",
    )


@router.get("/scanners")
def list_available_scanners():
    """List all registered security scanner engines (Standard, OWASP ZAP, ProjectDiscovery, CISA KEV)."""
    from src.services.crawler.scanners import ScannerFactory
    return {
        "scanners": ScannerFactory.list_available_scanners(),
    }


@router.get("/jobs", response_model=JobListResponse)
def list_crawler_jobs(
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
    jobs_service: JobsService = Depends(get_jobs_service),
):
    """List submitted crawler background jobs with status and summary metrics."""
    items, total = jobs_service.list_jobs(
        skip=skip,
        limit=limit,
        job_type="crawler_scan",
        status=status,
    )
    return JobListResponse(
        total=total,
        skip=skip,
        limit=limit,
        items=items,
    )


@router.get("/jobs/{job_id}", response_model=JobDetail)
def get_crawler_job(
    job_id: str,
    jobs_service: JobsService = Depends(get_jobs_service),
):
    """Get full status, progress, and discovery results for a crawl job."""
    job = jobs_service.get_job(job_id)
    if not job:
        raise NotFoundError(f"Crawl job '{job_id}' not found", code="JOB_NOT_FOUND")
    return job


@router.post("/jobs/{job_id}/retry", response_model=JobSubmitResponse)
def retry_crawler_job(
    job_id: str,
    jobs_service: JobsService = Depends(get_jobs_service),
):
    """Retry a failed or stalled crawler job."""
    try:
        retried_id = jobs_service.retry_job(job_id, auto_start=True)
        return JobSubmitResponse(
            success=True,
            job_id=retried_id,
            job_type="crawler_scan",
            status=JobStatus.QUEUED,
            message="Crawl job re-queued for execution",
        )
    except LookupError as e:
        raise NotFoundError(str(e), code="JOB_NOT_FOUND")


@router.post("/run")
def execute_crawler_run(
    req: CrawlerRunRequest,
    crawler: CrawlerService = Depends(get_crawler_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    """Execute domain-specific perimeter crawler synchronously."""
    if not req.domains:
        raise InvalidInputError("At least one target domain is required", code="MISSING_TARGET_DOMAINS")

    crawler.set_accounts_service(accounts_service)
    results = []

    for raw_dom in req.domains:
        clean = raw_dom.strip()
        if not clean:
            continue

        try:
            res = crawler.crawl_domain(
                domain=clean,
                scan_depth=req.scan_depth,
                scanner_type=req.scanner_type or "all",
                enable_subdomains=req.enable_subdomains,
                custom_ports=req.custom_ports,
                save_to_database=req.save_to_database,
            )
            results.append(res)
        except Exception as e:
            logger.error(f"Error crawling {clean}: {e}", exc_info=True)
            results.append({
                "domain": clean,
                "error": str(e),
                "assets_count": 0,
                "signals_detected_count": 0,
            })

    return {
        "success": True,
        "total_crawled": len(results),
        "results": results,
        "timestamp": datetime.now().isoformat(),
    }
