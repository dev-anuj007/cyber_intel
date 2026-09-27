from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends

from src.core.exceptions import InvalidInputError, NotFoundError
from src.services.auth.dependencies import get_current_user_optional
from src.services.crawler.dependencies import get_crawler_service
from src.services.crawler.protocols import ICrawlerService
from src.services.crawler.types import (
    CrawlerJobSubmitRequest,
    CrawlerRunRequest,
    CrawlerRunResponse,
    CrawlerScannersResponse,
    CrawlerScanRequest,
    CrawlerSingleScanResponse,
)
from src.services.jobs.dependencies import get_jobs_service
from src.services.jobs.protocols import IJobsService
from src.services.jobs.types import (
    JobDetail,
    JobListQuery,
    JobListResponse,
    JobStatus,
    JobSubmitResponse,
    SubmitJobCommand,
)
from src.services.logger.logger_service import get_logger

logger = get_logger("crawler.api")

router = APIRouter(prefix="/api/crawler", tags=["Domain Crawler"])


@router.post("/jobs", response_model=JobSubmitResponse, status_code=202)
async def submit_crawler_job(
    req: CrawlerJobSubmitRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    crawler: ICrawlerService = Depends(get_crawler_service),
    jobs_service: IJobsService = Depends(get_jobs_service),
):
    clean_domains = [
        d.strip().replace("https://", "").replace("http://", "").rstrip("/") for d in req.domains if d.strip()
    ]
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
        title = f"{clean_domains[0]}, {clean_domains[1]} (+{len(clean_domains) - 2} more)"

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
        SubmitJobCommand(
            job_type="crawler_scan",
            title=title,
            payload=payload,
            progress_total=len(clean_domains),
            user_id=user_id,
            max_retries=3,
            auto_start=True,
        )
    )

    return JobSubmitResponse(
        success=True,
        job_id=job_id,
        job_type="crawler_scan",
        status=JobStatus.QUEUED,
        message=f"Perimeter scan queued for {len(clean_domains)} domains",
    )


@router.get("/scanners", response_model=CrawlerScannersResponse)
async def list_available_scanners():
    from src.services.crawler.internals.scanners.factory import ScannerFactory

    return CrawlerScannersResponse(
        scanners=ScannerFactory.list_available_scanners(),
    )


@router.get("/jobs", response_model=JobListResponse)
async def list_crawler_jobs(
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
    jobs_service: IJobsService = Depends(get_jobs_service),
):
    items, total = jobs_service.list_jobs(
        JobListQuery(
            skip=skip,
            limit=limit,
            job_type="crawler_scan",
            status=status,
        )
    )
    return JobListResponse(
        total=total,
        skip=skip,
        limit=limit,
        items=items,
    )


@router.get("/jobs/{job_id}", response_model=JobDetail)
async def get_crawler_job(
    job_id: str,
    jobs_service: IJobsService = Depends(get_jobs_service),
):
    job = jobs_service.get_job(job_id)
    if not job:
        raise NotFoundError(f"Crawl job '{job_id}' not found", code="JOB_NOT_FOUND")
    return job


@router.post("/jobs/{job_id}/retry", response_model=JobSubmitResponse)
async def retry_crawler_job(
    job_id: str,
    jobs_service: IJobsService = Depends(get_jobs_service),
):
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


@router.post("/run", response_model=CrawlerRunResponse)
async def execute_crawler_run(
    req: CrawlerRunRequest,
    crawler: ICrawlerService = Depends(get_crawler_service),
):
    if not req.domains:
        raise InvalidInputError("At least one target domain is required", code="MISSING_TARGET_DOMAINS")

    results = []

    for raw_dom in req.domains:
        clean = raw_dom.strip()
        if not clean:
            continue

        try:
            domain_req = CrawlerScanRequest(
                domain=clean,
                scan_depth=req.scan_depth,
                scanner_type=req.scanner_type or "all",
                enable_subdomains=req.enable_subdomains,
                custom_ports=req.custom_ports,
                save_to_database=req.save_to_database,
            )
            res = await crawler.crawl_domain_async(domain_req)
            results.append(res.model_dump() if hasattr(res, "model_dump") else res)
        except Exception as e:
            logger.error(f"Error crawling {clean}: {e}", exc_info=True)
            results.append(
                {
                    "domain": clean,
                    "error": str(e),
                    "assets_count": 0,
                    "signals_detected_count": 0,
                }
            )

    return CrawlerRunResponse(
        success=True,
        total_crawled=len(results),
        results=results,
        timestamp=datetime.now().isoformat(),
    )


@router.post("/scan", response_model=CrawlerSingleScanResponse)
async def scan_domain_endpoint(
    req: CrawlerScanRequest,
    crawler: ICrawlerService = Depends(get_crawler_service),
):
    res = await crawler.scan_domain_async(req)
    return CrawlerSingleScanResponse(
        success=True,
        domain=req.domain,
        scanner_type=req.scanner_type,
        result=res,
    )

