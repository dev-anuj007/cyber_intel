from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.services.accounts.internals.repositories.writer import AccountWriter
from src.services.accounts.types import Account, Asset, SecuritySignal, SignalSeverity
from src.services.database.database_service import DatabaseService
from src.services.scorer.api import get_scorer_service, router
from src.services.scorer.dependencies import create_scorer_service
from src.services.scorer.types import AccountScore, PriorityTier, ScoreAccountCommand


@pytest.fixture
def test_db(tmp_path):
    db_path = str(tmp_path / "test_scorer_comp.db")
    db_service = DatabaseService(db_path=db_path)
    db_service.init_database()
    return db_path


@pytest.fixture
def scorer_service(test_db):
    return create_scorer_service(db_path=test_db)


@pytest.fixture
def scored_account():
    return Account(
        account_key="domain:testtarget.com",
        domains=["testtarget.com"],
        assets=[Asset(ip="192.168.1.1", port=443, hostname="testtarget.com")],
        ips=["192.168.1.1"],
        hostnames=["testtarget.com"],
        ports=[443],
        products=["Apache HTTP Server"],
        cloud_providers=["AWS"],
        signals=[
            SecuritySignal(
                name="cve_vulnerability",
                severity=SignalSeverity.CRITICAL,
                category="vulnerability",
                evidence="CVE-2023-9999",
            )
        ],
    )


def test_scorer_repositories_and_service_crud(scorer_service, scored_account, test_db):
    ctx = scorer_service.format_account_context(scored_account)
    assert "testtarget.com" in ctx
    assert "CVE-2023-9999" in ctx

    score = AccountScore(
        account_key="domain:testtarget.com",
        account=scored_account,
        version=1,
        score=95,
        priority_tier=PriorityTier.TIER_1_CRITICAL,
        key_risks=["CVE-2023-9999 Exploit"],
        suggested_outreach="Urgent patch advisory",
        score_rationale="Active critical CVE detected",
        model_version="v2.0",
        model_name="gemini-3.1-flash-lite",
        tokens_used={"prompt_tokens": 500, "completion_tokens": 150},
        latency_ms=320,
        cost_usd=0.00045,
        timestamp=datetime.now(timezone.utc),
    )
    saved = scorer_service.save_score(score)
    assert saved is not None
    assert saved["score"] == 95
    assert saved["priority_tier"] == "tier_1_critical"

    latest = scorer_service.get_latest_score("domain:testtarget.com")
    assert latest is not None
    assert latest["score"] == 95

    score2 = AccountScore(
        account_key="domain:testtarget.com",
        account=scored_account,
        version=2,
        score=80,
        priority_tier=PriorityTier.TIER_2_HIGH,
        key_risks=["High severity patch needed"],
        suggested_outreach="Security notification",
        score_rationale="Score lowered after mitigations",
        model_version="v2.0",
        model_name="gemini-3.1-flash-lite",
        tokens_used={"prompt_tokens": 450, "completion_tokens": 120},
        latency_ms=280,
        cost_usd=0.00038,
        timestamp=datetime.now(timezone.utc),
    )
    saved2 = scorer_service.save_score(score2)
    assert saved2["version"] == 2

    history = scorer_service.get_score_history("domain:testtarget.com")
    assert len(history) == 2

    latest2 = scorer_service.get_latest_score("domain:testtarget.com")
    assert latest2["version"] == 2
    assert latest2["score"] == 80


def test_scorer_ai_scoring_mocked(scorer_service, scored_account, test_db):
    mock_response = MagicMock()
    mock_response.text = '{"score": 90, "priority_tier": "tier_1_critical", "key_risks": ["Active exploit"], "suggested_outreach": "Contact CISO", "score_rationale": "High risk account"}'
    mock_response.usage_metadata.prompt_token_count = 600
    mock_response.usage_metadata.candidates_token_count = 120

    acc_writer = AccountWriter()
    db_svc = DatabaseService(db_path=test_db)
    with db_svc.get_connection() as conn:
        acc_writer.insert_account(conn, scored_account, "tier_1_critical")
        conn.commit()

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    scorer_service.client = mock_client

    scored = scorer_service.score_account(ScoreAccountCommand(account=scored_account))
    assert scored is not None
    assert scored.score == 90
    assert scored.priority_tier == PriorityTier.TIER_1_CRITICAL


def test_scorer_api_endpoints(scorer_service, scored_account, test_db):
    api_app = FastAPI()
    api_app.include_router(router)
    api_app.dependency_overrides[get_scorer_service] = lambda: scorer_service
    client = TestClient(api_app)

    db_svc = DatabaseService(db_path=test_db)
    with db_svc.get_connection() as conn:
        scorer_service.writer.save_score(
            conn,
            {
                "account_key": "domain:testtarget.com",
                "version": 1,
                "score": 85,
                "priority_tier": "tier_2_high",
                "key_risks": ["Vulnerability X"],
                "suggested_outreach": "Outreach Y",
                "score_rationale": "High risk",
                "model_version": "v2.0",
                "model_name": "gemini-3.1-flash-lite",
                "tokens_used": {"prompt": 100, "completion": 50},
                "latency_ms": 150,
                "cost_usd": 0.0001,
            },
        )
        conn.commit()

    r = client.get("/api/scores/latest/domain:testtarget.com")
    assert r.status_code == 200
    assert r.json()["score"] == 85

    r = client.get("/api/scores/history/domain:testtarget.com")
    assert r.status_code == 200
    assert len(r.json()) >= 1

    api_app.dependency_overrides.clear()
