"""Comprehensive Pytest Test Suite for Crawler Service, Scanners, Repositories, and API."""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.services.crawler.api import get_crawler_service, router
from src.services.crawler.crawler_service import CrawlerService
from src.services.crawler.repositories.jobs_repository import CrawlerJobsRepository
from src.services.crawler.scanners.cisa_kev_scanner import CisaKevScanner
from src.services.crawler.scanners.factory import ScannerFactory
from src.services.crawler.scanners.owasp_zap_scanner import OwaspZapScanner
from src.services.crawler.scanners.projectdiscovery_scanner import ProjectDiscoveryScanner
from src.services.crawler.scanners.standard_scanner import StandardCrawlerScanner
from src.services.database.database_service import DatabaseService


@pytest.fixture
def test_db(tmp_path):
    db_path = str(tmp_path / "test_crawler_comp.db")
    db_service = DatabaseService(db_path=db_path)
    db_service.init_database()
    return db_path


@pytest.fixture
def crawler_service(test_db):
    repo = CrawlerJobsRepository(db_path=test_db)
    return CrawlerService(jobs_repo=repo, db_path=test_db)


def test_scanner_factory():
    scanners = ScannerFactory.list_available_scanners()
    assert len(scanners) >= 4

    # Get scanner instances
    s1 = ScannerFactory.get_scanner("standard")
    assert isinstance(s1, StandardCrawlerScanner)

    s2 = ScannerFactory.get_scanner("owasp_zap")
    assert isinstance(s2, OwaspZapScanner)

    s3 = ScannerFactory.get_scanner("projectdiscovery")
    assert isinstance(s3, ProjectDiscoveryScanner)

    s4 = ScannerFactory.get_scanner("cisa_kev")
    assert isinstance(s4, CisaKevScanner)


def test_standard_scanner_mocked():
    scanner = StandardCrawlerScanner()
    with (
        patch("socket.gethostbyname", return_value="93.184.216.34"),
        patch("socket.gethostbyaddr", return_value=("example.com", [], ["93.184.216.34"])),
    ):
        results = scanner.scan("example.com")
        assert results is not None
        assert results.domain == "example.com"
        assert len(results.assets) >= 1


def test_owasp_zap_scanner_mocked():
    scanner = OwaspZapScanner()
    with patch("socket.gethostbyname", return_value="1.2.3.4"):
        results = scanner.scan("testcorp.org")
        assert results is not None
        assert results.domain == "testcorp.org"


def test_projectdiscovery_scanner_mocked():
    scanner = ProjectDiscoveryScanner()
    with patch("socket.gethostbyname", return_value="52.1.2.3"):
        results = scanner.scan("cloudtarget.io")
        assert results is not None
        assert results.domain == "cloudtarget.io"


def test_cisa_kev_scanner_mocked():
    scanner = CisaKevScanner()
    with patch("socket.gethostbyname", return_value="10.0.0.5"):
        results = scanner.scan("threattarget.net")
        assert results is not None
        assert results.domain == "threattarget.net"


def test_scanner_factory_run_scan():
    with patch("socket.gethostbyname", return_value="8.8.8.8"):
        result = ScannerFactory.run_scan("allscanners.com", scanner_type="all")
        assert result is not None
        assert result.domain == "allscanners.com"


def test_crawler_service_and_jobs_repo(crawler_service, test_db):
    # Test scan
    with patch("socket.gethostbyname", return_value="1.2.3.4"):
        result = crawler_service.scan_domain("scanme.org", scanner_type="standard")
        assert result is not None

    # Test jobs repository
    repo = CrawlerJobsRepository(db_path=test_db)
    job_id = repo.create_job("scanme.org", "standard")
    assert job_id is not None

    job = repo.get_job(job_id)
    assert job is not None
    assert job["domain"] == "scanme.org"
    assert job["status"] == "pending"

    # Update progress & status
    repo.update_job_status(job_id, "running", progress=50)
    job = repo.get_job(job_id)
    assert job is not None
    assert job["status"] == "running"
    assert job["progress"] == 50

    # Complete job
    repo.complete_job(job_id, results_summary={"signals": 5, "assets": 2})
    job = repo.get_job(job_id)
    assert job is not None
    assert job["status"] == "completed"
    assert job["progress"] == 100

    # Fail job
    fail_job_id = repo.create_job("faildomain.com", "standard")
    repo.fail_job(fail_job_id, "Network timeout")
    job_fail = repo.get_job(fail_job_id)
    assert job_fail is not None
    assert job_fail["status"] == "failed"
    assert "timeout" in (job_fail.get("error_message") or "")

    # List jobs
    jobs = repo.list_jobs(limit=10)
    assert len(jobs) >= 2


def test_crawler_api_endpoints(crawler_service):
    api_app = FastAPI()
    api_app.include_router(router)
    api_app.dependency_overrides[get_crawler_service] = lambda: crawler_service
    client = TestClient(api_app)

    # List scanners
    r = client.get("/api/crawler/scanners")
    assert r.status_code == 200
    scanners = r.json().get("scanners", r.json()) if isinstance(r.json(), dict) else r.json()
    assert len(scanners) >= 4

    # Trigger scan
    with patch("socket.gethostbyname", return_value="1.2.3.4"):
        r = client.post("/api/crawler/scan", json={"domain": "apicrawl.com", "scanner_type": "standard"})
        assert r.status_code in [200, 422]

    # List jobs
    r = client.get("/api/crawler/jobs")
    assert r.status_code == 200

    api_app.dependency_overrides.clear()


def test_crawler_invalid_domain_raises_error(crawler_service):
    with pytest.raises(ValueError, match="could not be resolved via DNS or does not exist"):
        crawler_service.crawl_domain("hjhjkjhkjhkhk.com")


def test_crawler_job_handles_invalid_domain_cleanly(crawler_service):
    progress_calls = []
    res = crawler_service.handle_crawler_job_scan(
        job_id="job-test-invalid",
        payload={"domains": ["invalid-fake-domain-12345.xyz"], "scanner_type": "all", "save_to_database": False},
        progress_cb=lambda cur, tot, metadata=None, partial_results=None: progress_calls.append(cur),
    )
    assert len(res["results"]) == 1
    assert res["results"][0]["assets_count"] == 0
    assert res["results"][0]["signals_detected_count"] == 0
    assert "could not be resolved" in res["results"][0]["error"]
