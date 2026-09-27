import asyncio
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.services.crawler.api import get_crawler_service, router
from src.services.crawler.crawler_service import CrawlerService
from src.services.crawler.dependencies import get_crawler_dependency_context
from src.services.crawler.internals.scanners.cisa_kev_scanner import CisaKevScanner
from src.services.crawler.internals.scanners.factory import ScannerFactory
from src.services.crawler.internals.scanners.owasp_zap_scanner import OwaspZapScanner
from src.services.crawler.internals.scanners.projectdiscovery_scanner import (
    ProjectDiscoveryScanner,
)
from src.services.crawler.internals.scanners.standard_scanner import (
    StandardCrawlerScanner,
)
from src.services.crawler.types import (
    CrawlerRunRequest,
    CrawlerScanRequest,
)
from src.services.database.database_service import DatabaseService
from src.services.jobs.dependencies import create_jobs_service, get_jobs_service


@pytest.fixture
def test_db(tmp_path):
    db_path = str(tmp_path / "test_crawler_comp.db")
    db_service = DatabaseService(db_path=db_path)
    db_service.init_database()
    return db_path


@pytest.fixture
def crawler_service(test_db):
    ctx = get_crawler_dependency_context(db_path=test_db)
    return CrawlerService(context=ctx)


@pytest.fixture
def jobs_service(test_db):
    return create_jobs_service(db_path=test_db)


def test_scanner_factory():
    scanners = ScannerFactory.list_available_scanners()
    assert len(scanners) >= 4

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


def test_async_scanner_factory_and_scanners():
    with patch("socket.gethostbyname", return_value="8.8.8.8"):
        result = asyncio.run(ScannerFactory.run_scan_async("allscanners.com", scanner_type="all"))
        assert result is not None
        assert result.domain == "allscanners.com"


def test_crawler_service_scan_domain(crawler_service):
    with patch("socket.gethostbyname", return_value="1.2.3.4"):
        result = crawler_service.scan_domain(CrawlerScanRequest(domain="scanme.org", scanner_type="standard"))
        assert result is not None
        assert result.domain == "scanme.org"


def test_crawler_api_endpoints(crawler_service, jobs_service):
    api_app = FastAPI()
    api_app.include_router(router)
    api_app.dependency_overrides[get_crawler_service] = lambda: crawler_service
    api_app.dependency_overrides[get_jobs_service] = lambda: jobs_service
    client = TestClient(api_app)

    r = client.get("/api/crawler/scanners")
    assert r.status_code == 200
    scanners = r.json().get("scanners", r.json()) if isinstance(r.json(), dict) else r.json()
    assert len(scanners) >= 4

    with patch("socket.gethostbyname", return_value="1.2.3.4"):
        r = client.post("/api/crawler/scan", json={"domain": "apicrawl.com", "scanner_type": "standard"})
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["domain"] == "apicrawl.com"

    r = client.post(
        "/api/crawler/jobs",
        json={
            "domains": ["apicrawl.com"],
            "pipeline_name": "Test Crawl Pipeline",
            "scanner_type": "standard",
        },
    )
    assert r.status_code == 202
    job_info = r.json()
    assert job_info["success"] is True
    assert "job_id" in job_info

    r = client.get("/api/crawler/jobs")
    assert r.status_code == 200

    api_app.dependency_overrides.clear()


def test_crawler_invalid_domain_raises_error(crawler_service):
    with pytest.raises(ValueError, match="could not be resolved via DNS or does not exist"):
        crawler_service.crawl_domain(CrawlerScanRequest(domain="hjhjkjhkjhkhk.com"))


def test_crawler_job_handles_invalid_domain_cleanly(crawler_service):
    progress_calls = []
    res = crawler_service.handle_crawler_job_scan(
        job_id="job-test-invalid",
        request=CrawlerRunRequest(
            domains=["invalid-fake-domain-12345.xyz"], scanner_type="all", save_to_database=False
        ),
        progress_cb=lambda cur, tot, metadata=None, partial_results=None: progress_calls.append(cur),
    )
    assert len(res.results) == 1
    assert res.results[0]["assets_count"] == 0
    assert res.results[0]["signals_detected_count"] == 0
    assert "could not be resolved" in res.results[0]["error"]
