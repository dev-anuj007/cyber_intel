import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.services.database.database_service import DatabaseService
from src.services.jobs.api import get_jobs_service, router
from src.services.jobs.dependencies import (
    create_jobs_service,
    get_jobs_dependency_context,
)
from src.services.jobs.jobs_service import JobsService
from src.services.jobs.protocols import IJobsReader, IJobsService, IJobsWriter
from src.services.jobs.types import (
    CompleteJobCommand,
    CreateJobRequest,
    JobListQuery,
    JobStatus,
    UpdateProgressCommand,
)


@pytest.fixture
def test_db(tmp_path):
    db_path = str(tmp_path / "test_jobs_comp.db")
    db_service = DatabaseService(db_path=db_path)
    db_service.init_database()
    return db_path


@pytest.fixture
def jobs_service(test_db):
    ctx = get_jobs_dependency_context(db_path=test_db)
    return JobsService(ctx)


def test_jobs_service_protocols_and_dependencies(test_db):
    ctx = get_jobs_dependency_context(db_path=test_db)
    assert isinstance(ctx.reader, IJobsReader)
    assert isinstance(ctx.writer, IJobsWriter)

    svc = create_jobs_service(context=ctx, db_path=test_db)
    assert isinstance(svc, IJobsService)


def test_jobs_service_lifecycle(jobs_service):
    job = jobs_service.create_job(
        CreateJobRequest(
            job_type="crawler",
            payload={"domain": "testjobs.com", "engine": "standard"},
            description="Crawling testjobs.com",
        )
    )
    assert job is not None
    job_id = job.job_id
    assert job.status == JobStatus.PENDING

    fetched = jobs_service.get_job(job_id)
    assert fetched is not None
    assert fetched.job_id == job_id
    assert fetched.payload["domain"] == "testjobs.com"

    jobs_service.update_job_progress(
        UpdateProgressCommand(job_id=job_id, current=45, total=100),
        status=JobStatus.RUNNING,
    )
    f2 = jobs_service.get_job(job_id)
    assert f2.status == JobStatus.RUNNING
    assert f2.progress == 45

    jobs_service.complete_job(
        CompleteJobCommand(
            job_id=job_id,
            results={"total_signals": 10, "account_key": "domain:testjobs.com"},
        )
    )
    f3 = jobs_service.get_job(job_id)
    assert f3.status == JobStatus.COMPLETED
    assert f3.progress == 100
    assert f3.result["total_signals"] == 10

    fail_job = jobs_service.create_job(CreateJobRequest(job_type="scorer", payload={"account_key": "domain:fail.com"}))
    jobs_service.fail_job(fail_job.job_id, error="Scoring timeout occurred")
    f_fail = jobs_service.get_job(fail_job.job_id)
    assert f_fail.status == JobStatus.FAILED
    assert "timeout" in f_fail.error

    cancel_job = jobs_service.create_job(CreateJobRequest(job_type="eval", payload={"version": "v1"}))
    jobs_service.cancel_job(cancel_job.job_id)
    f_cancel = jobs_service.get_job(cancel_job.job_id)
    assert f_cancel.status == JobStatus.CANCELLED

    jobs, total = jobs_service.list_jobs(JobListQuery(limit=10))
    assert total >= 3
    assert len(jobs) >= 3


def test_jobs_api_endpoints(jobs_service):
    api_app = FastAPI()
    api_app.include_router(router)
    api_app.dependency_overrides[get_jobs_service] = lambda: jobs_service
    client = TestClient(api_app)

    r = client.post(
        "/api/jobs",
        json={
            "job_type": "crawler",
            "title": "Crawl domain",
            "payload": {"domain": "api-job.com"},
        },
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    r = client.get(f"/api/jobs/{job_id}")
    assert r.status_code == 200
    assert r.json()["job_id"] == job_id

    r = client.get("/api/jobs")
    assert r.status_code == 200
    assert "items" in r.json()

    r = client.post(f"/api/jobs/{job_id}/cancel")
    assert r.status_code == 200

    api_app.dependency_overrides.clear()


def test_job_dispatchers(test_db):
    from src.services.jobs.internals.dispatchers import (
        LambdaJobDispatcher,
        ThreadPoolJobDispatcher,
    )
    from src.services.jobs.protocols import IJobDispatcher

    executed = []

    def mock_executor(job_id: str):
        executed.append(job_id)

    tp_dispatcher = ThreadPoolJobDispatcher(executor_fn=mock_executor)
    assert isinstance(tp_dispatcher, IJobDispatcher)
    tp_dispatcher.dispatch("test_job_1", "crawler")

    import time
    time.sleep(0.05)
    assert "test_job_1" in executed

    lambda_dispatcher = LambdaJobDispatcher(
        fallback_dispatcher=tp_dispatcher,
        app_name="app",
        environment="test",
        region="us-east-1",
    )
    assert isinstance(lambda_dispatcher, IJobDispatcher)
    assert lambda_dispatcher._resolve_function_name("crawler_job") == "app-test-crawler"
    assert lambda_dispatcher._resolve_function_name("eval_job") == "app-test-eval"
    assert lambda_dispatcher._resolve_function_name("scorer_job") == "app-test-scorer"
    assert lambda_dispatcher._resolve_function_name("unknown") == "app-test-jobs"


def test_cancellation_protection_during_execution(jobs_service):
    def dummy_handler(job_id, payload, progress_callback):
        progress_callback(50, 100)
        jobs_service.cancel_job(job_id)
        return {"done": True}

    jobs_service.register_handler("cancelling_type", dummy_handler)
    job = jobs_service.create_job(CreateJobRequest(job_type="cancelling_type", payload={}))
    jobs_service.execute_job(job.job_id)

    final_job = jobs_service.get_job(job.job_id)
    assert final_job.status == JobStatus.CANCELLED
    assert final_job.results is None


def test_stale_job_recovery_threshold(jobs_service):
    job = jobs_service.create_job(CreateJobRequest(job_type="stale_test", payload={}))
    jobs_service._writer.start_job(job.job_id)
    assert jobs_service.get_job(job.job_id).status == JobStatus.RUNNING

    # 1. Recovery with large threshold (e.g. 3600 seconds) shouldn't reset brand new running job
    count = jobs_service.recover_stale_jobs(stale_threshold_seconds=3600)
    assert count == 0
    assert jobs_service.get_job(job.job_id).status == JobStatus.RUNNING

    # 2. Recovery without threshold resets all running jobs
    count2 = jobs_service.recover_stale_jobs(stale_threshold_seconds=0)
    assert count2 >= 1
    assert jobs_service.get_job(job.job_id).status == JobStatus.QUEUED

