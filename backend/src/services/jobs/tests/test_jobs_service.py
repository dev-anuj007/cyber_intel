"""Comprehensive Pytest Test Suite for Jobs Service, Repository, and API."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.services.database.database_service import DatabaseService
from src.services.jobs.api import get_jobs_service, router
from src.services.jobs.jobs_service import JobsService
from src.services.jobs.repositories.jobs_repository import JobsRepository
from src.services.jobs.types import JobStatus


@pytest.fixture
def test_db(tmp_path):
    db_path = str(tmp_path / "test_jobs_comp.db")
    db_service = DatabaseService(db_path=db_path)
    db_service.init_database()
    return db_path


@pytest.fixture
def jobs_service(test_db):
    repo = JobsRepository(db_path=test_db)
    return JobsService(repository=repo, db_path=test_db)


def test_jobs_service_lifecycle(jobs_service, test_db):
    # 1. Create job
    job = jobs_service.create_job(
        job_type="crawler",
        payload={"domain": "testjobs.com", "engine": "standard"},
        description="Crawling testjobs.com",
    )
    assert job is not None
    job_id = job.job_id
    assert job.status == JobStatus.PENDING

    # 2. Get job
    fetched = jobs_service.get_job(job_id)
    assert fetched is not None
    assert fetched.job_id == job_id
    assert fetched.payload["domain"] == "testjobs.com"

    # 3. Update progress
    jobs_service.update_job_progress(job_id, progress=45, status=JobStatus.RUNNING)
    f2 = jobs_service.get_job(job_id)
    assert f2.status == JobStatus.RUNNING
    assert f2.progress == 45

    # 4. Complete job
    jobs_service.complete_job(job_id, result={"total_signals": 10, "account_key": "domain:testjobs.com"})
    f3 = jobs_service.get_job(job_id)
    assert f3.status == JobStatus.COMPLETED
    assert f3.progress == 100
    assert f3.result["total_signals"] == 10

    # 5. Fail job
    fail_job = jobs_service.create_job(job_type="scorer", payload={"account_key": "domain:fail.com"})
    jobs_service.fail_job(fail_job.job_id, error="Scoring timeout occurred")
    f_fail = jobs_service.get_job(fail_job.job_id)
    assert f_fail.status == JobStatus.FAILED
    assert "timeout" in f_fail.error

    # 6. Cancel job
    cancel_job = jobs_service.create_job(job_type="eval", payload={"version": "v1"})
    jobs_service.cancel_job(cancel_job.job_id)
    f_cancel = jobs_service.get_job(cancel_job.job_id)
    assert f_cancel.status == JobStatus.CANCELLED

    # 7. List jobs
    jobs, total = jobs_service.list_jobs(limit=10)
    assert total >= 3
    assert len(jobs) >= 3


def test_jobs_api_endpoints(jobs_service):
    api_app = FastAPI()
    api_app.include_router(router)
    api_app.dependency_overrides[get_jobs_service] = lambda: jobs_service
    client = TestClient(api_app)

    # Create job
    r = client.post(
        "/api/jobs",
        json={"job_type": "crawler", "title": "Crawl domain", "payload": {"domain": "api-job.com"}},
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    # Get job
    r = client.get(f"/api/jobs/{job_id}")
    assert r.status_code == 200
    assert r.json()["job_id"] == job_id

    # List jobs
    r = client.get("/api/jobs")
    assert r.status_code == 200
    assert "items" in r.json()

    # Cancel job
    r = client.post(f"/api/jobs/{job_id}/cancel")
    assert r.status_code == 200

    api_app.dependency_overrides.clear()
