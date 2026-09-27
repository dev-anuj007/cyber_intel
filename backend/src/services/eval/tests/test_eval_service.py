from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.services.database.database_service import DatabaseService
from src.services.eval.api import get_eval_service, router
from src.services.eval.dependencies import create_eval_service
from src.services.eval.eval_harness import EvalResult
from src.services.eval.internals.repositories.reader import EvalReader
from src.services.eval.internals.repositories.writer import EvalWriter
from src.services.eval.types import ComparePromptsCommand, RunEvalCommand


@pytest.fixture
def test_db(tmp_path):
    db_path = str(tmp_path / "test_eval_comp.db")
    db_service = DatabaseService(db_path=db_path)
    db_service.init_database()
    return db_path


@pytest.fixture
def eval_service(test_db):
    return create_eval_service(db_path=test_db)


def test_eval_service_harness_and_runs(eval_service, test_db):
    prompts = eval_service.list_prompts()
    assert len(prompts) >= 1

    bench_res = eval_service.run_eval(RunEvalCommand(prompt_version="v2.0", dry_run=True, sample_limit=2))
    assert bench_res is not None
    assert bench_res["prompt_version"] == "v2.0"

    history = eval_service.list_history()
    assert isinstance(history, list)

    writer = EvalWriter()
    reader = EvalReader()
    db_svc = DatabaseService(db_path=test_db)
    conn = db_svc.get_connection()

    try:
        run_record = {
            "run_id": "run-test-12345",
            "prompt_version": "v2.0",
            "dataset_type": "synthetic_benchmark",
            "sample_size": 10,
            "accuracy": 0.95,
            "precision": 0.92,
            "recall": 0.94,
            "f1_score": 0.93,
            "cost_usd": 0.005,
            "avg_latency_ms": 250,
            "status": "completed",
            "metrics_json": '{"detailed": true}',
            "created_at": "2026-09-18T12:00:00Z",
        }
        writer.save_run(conn, run_record)

        fetched = reader.get_run_by_id(conn, "run-test-12345")
        assert fetched is not None
        assert fetched["run_id"] == "run-test-12345"
        assert fetched["accuracy"] == 0.95

        runs = reader.get_runs(conn, prompt_version="v2.0", limit=5)
        assert len(runs) >= 1
    finally:
        conn.close()


def test_eval_harness_computations():
    res = EvalResult(prompt_version="v2.0")
    res.add_prediction(
        expected_tier="tier_1_critical",
        predicted_tier="tier_1_critical",
        expected_score=95,
        predicted_score=95,
        key_risks=["Exploit A"],
        suggested_outreach="Action A",
    )
    assert res.total == 1


def test_eval_api_endpoints(eval_service):
    api_app = FastAPI()
    api_app.include_router(router)
    api_app.dependency_overrides[get_eval_service] = lambda: eval_service
    client = TestClient(api_app)

    r = client.get("/api/eval/prompts")
    assert r.status_code == 200

    r = client.post("/api/eval/run", json={"prompt_version": "v2.0", "sample_limit": 2, "dry_run": True})
    assert r.status_code in [200, 202, 422]
    if r.status_code == 202:
        data = r.json()
        assert data["success"] is True
        assert "job_id" in data
        assert data["job_type"] == "eval_run"

    r = client.post(
        "/api/eval/compare", json={"prompt_a": "v1.0", "prompt_b": "v2.0", "sample_limit": 2, "dry_run": True}
    )
    assert r.status_code in [200, 202, 422]
    if r.status_code == 202:
        data = r.json()
        assert data["success"] is True
        assert "job_id" in data

    r = client.get("/api/eval/history")
    assert r.status_code == 200

    api_app.dependency_overrides.clear()


def test_eval_job_handler(eval_service):
    progress_updates = []

    def mock_progress(current, total, metadata=None, partial=None):
        progress_updates.append((current, total, metadata))

    job_payload = {
        "prompt_version": "v2.0",
        "dry_run": True,
        "sample_limit": 2,
    }

    result = eval_service.handle_eval_job("job_eval_test_123", job_payload, mock_progress)
    assert "results" in result
    assert result["results"]["success"] is True
    assert "metadata" in result
    assert result["metadata"]["total_samples"] == 2
    assert len(progress_updates) >= 1


def test_eval_compare_job_handler(eval_service):
    progress_updates = []

    def mock_progress(current, total, metadata=None, partial=None):
        progress_updates.append((current, total, metadata))

    job_payload = {
        "prompt_a": "v1.0",
        "prompt_b": "v2.0",
        "dry_run": True,
        "sample_limit": 2,
    }

    result = eval_service.handle_eval_compare_job("job_compare_test_123", job_payload, mock_progress)
    assert "results" in result
    assert result["results"]["success"] is True
    assert "comparison" in result["results"]
    assert "metadata" in result
    assert len(progress_updates) >= 1


def test_eval_service_compare_with_files():
    mock_reader = MagicMock()
    mock_reader.read_result_file.side_effect = lambda results_dir, fname: {
        "results": {
            "prompt_version": fname,
            "total": 5,
            "tier_accuracy": 0.8,
            "predictions": [],
        }
    }
    svc = create_eval_service(reader=mock_reader, writer=MagicMock())
    result = svc.compare_prompts(ComparePromptsCommand(file_a="file_a.json", file_b="file_b.json"))
    assert result["success"] is True
    assert "comparison" in result
    assert mock_reader.read_result_file.call_count == 2
