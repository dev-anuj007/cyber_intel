"""Comprehensive Pytest Test Suite for Database Service and API."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.services.database import is_deployed
from src.services.database.api import get_db_service, router
from src.services.database.database_service import DatabaseService


@pytest.fixture
def test_db(tmp_path):
    db_path = str(tmp_path / "test_db_service.db")
    return db_path


@pytest.fixture
def db_service(test_db):
    return DatabaseService(db_path=test_db)


def test_database_service_lifecycle(db_service, test_db):
    # 1. Initialize schema
    db_service.init_database()

    # 2. Get connection and check tables
    with db_service.get_connection() as conn:
        assert conn is not None
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        assert "accounts" in tables
        assert "domains" in tables
        assert "assets" in tables
        assert "signals" in tables
        assert "ai_scores" in tables
        assert "users" in tables
        assert "crawler_jobs" in tables
        assert "eval_runs" in tables

    # 3. Execute update and query
    db_service.execute_update(
        "INSERT INTO accounts (account_key, priority_tier) VALUES (?, ?)",
        ("domain:dbtest.com", "tier_2_high"),
    )

    rows = db_service.execute_query(
        "SELECT account_key, priority_tier FROM accounts WHERE account_key = ?",
        ("domain:dbtest.com",),
    )
    assert len(rows) == 1
    assert rows[0][0] == "domain:dbtest.com"

    # 4. Execute batch
    db_service.execute_batch(
        "INSERT INTO domains (account_id, domain) VALUES (?, ?)",
        [(1, "dbtest.com"), (1, "api.dbtest.com")],
    )

    # 5. Get table stats
    stats = db_service.get_table_stats()
    assert stats["accounts"] >= 1
    assert stats["domains"] >= 2


def test_is_deployed_helper():
    assert isinstance(is_deployed(), bool)


def test_database_api_endpoints(db_service):
    db_service.init_database()
    api_app = FastAPI()
    api_app.include_router(router)
    api_app.dependency_overrides[get_db_service] = lambda: db_service
    client = TestClient(api_app)

    # Health
    r = client.get("/api/database/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "engine" in data

    # Stats
    r = client.get("/api/database/stats")
    assert r.status_code == 200

    # Query
    r = client.post("/api/database/query", json={"sql": "SELECT COUNT(*) FROM accounts", "params": []})
    assert r.status_code == 200

    api_app.dependency_overrides.clear()
